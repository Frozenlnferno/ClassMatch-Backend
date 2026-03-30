import io
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import jwt
from jwt.exceptions import InvalidTokenError
from cryptography.hazmat.primitives.asymmetric import ec

from app import create_app
from app.config import Config
from app.routes.groups import groups_service
from app.utils.auth import verify_supabase_jwt


class _DummySigningKey:
    def __init__(self, key):
        self.key = key


class _DummyJwksClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, _token):
        return _DummySigningKey(self._key)


class _FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self._fetchone_values = list(fetchone_values or [])
        self._fetchall_values = list(fetchall_values or [])
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        if not self._fetchone_values:
            return None
        return self._fetchone_values.pop(0)

    def fetchall(self):
        if not self._fetchall_values:
            return []
        return self._fetchall_values.pop(0)


class BackendRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.config_patcher = patch.multiple(
            Config,
            FRONTEND_ORIGIN="http://localhost:5173",
            SUPABASE_URL="http://127.0.0.1:54321",
            SUPABASE_SECRET_KEY="sb_secret_test",
            SUPABASE_JWT_ISSUER="http://127.0.0.1:54321/auth/v1",
            SUPABASE_JWT_AUDIENCE="authenticated",
            SUPABASE_HTTP_TIMEOUT_SECONDS=20.0,
            UIUC_API_TIMEOUT_SECONDS=5.0,
            MAX_IMAGE_UPLOAD_BYTES=16,
            MAX_PDF_UPLOAD_BYTES=32,
            MAX_MANUAL_COURSES_PER_REQUEST=2,
            DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres",
            DB_SSLMODE="disable",
            LOG_OPTIONS_REQUESTS=False,
            SUPABASE_SCHEDULE_PDF_BUCKET="schedule-pdfs",
            SUPABASE_SCHEDULE_PDF_PREFIX="schedule-imports",
            REDIS_URL="redis://localhost:6379/0",
            REDIS_JOB_LEASE_SECONDS=60,
            REDIS_JOB_HEARTBEAT_SECONDS=20,
            REDIS_JOB_MAX_ATTEMPTS=3,
            REDIS_JOB_RETRY_BASE_DELAY_SECONDS=5,
            REDIS_JOB_RESULT_TTL_SECONDS=86400,
            REDIS_JOB_POLL_INTERVAL_SECONDS=0.01,
            JWKS_URL="http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        )
        self.config_patcher.start()
        self.init_db_pool_patcher = patch("app.init_db_pool", return_value=None)
        self.init_redis_patcher = patch("app.init_redis", return_value=None)
        self.init_db_pool_patcher.start()
        self.init_redis_patcher.start()
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.init_redis_patcher.stop()
        self.init_db_pool_patcher.stop()
        self.config_patcher.stop()

    def _auth_header(self, sub="user-1"):
        claims = {
            "sub": sub,
            "aud": Config.SUPABASE_JWT_AUDIENCE,
            "iss": Config.SUPABASE_JWT_ISSUER,
        }
        verifier_patcher = patch("app.utils.auth.verify_supabase_jwt", return_value=claims)
        self.addCleanup(verifier_patcher.stop)
        verifier_patcher.start()
        return {"Authorization": "Bearer test-token"}

    def test_group_members_returns_404_for_non_member(self):
        with patch("app.routes.groups.groups_controller.get_group_members", side_effect=PermissionError("Group not found")):
            response = self.client.get("/api/groups/12/members", headers=self._auth_header())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Group not found")

    def test_matching_classmates_returns_404_for_non_member(self):
        with patch("app.routes.schedules.schedules_controller.get_matching_classmates", side_effect=PermissionError("Group not found")):
            response = self.client.get(
                "/api/schedules/matching-classmates?group_id=12&term=fall&year=2026",
                headers=self._auth_header(),
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Group not found")

    def test_change_role_rejects_owner_role(self):
        response = self.client.post(
            "/api/groups/12/change-role",
            json={"member_id": "user-2", "new_role": "owner"},
            headers=self._auth_header(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Invalid role specified")

    def test_avatar_upload_rejects_oversized_image(self):
        response = self.client.post(
            "/api/users/me/avatar",
            data={"image": (io.BytesIO(b"x" * 32), "avatar.png")},
            headers=self._auth_header(),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("smaller than", response.get_json()["error"])

    def test_schedule_upload_rejects_oversized_pdf(self):
        response = self.client.post(
            "/api/schedules/",
            data={"pdf": (io.BytesIO(b"x" * 64), "schedule.pdf")},
            headers=self._auth_header(),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("smaller than", response.get_json()["error"])

    def test_manual_course_add_rejects_large_batch(self):
        response = self.client.post(
            "/api/schedules/courses?term=fall&year=2026",
            json={
                "courses": [
                    {"subject": "CS", "course": "101", "crn": "12345"},
                    {"subject": "MATH", "course": "241", "crn": "23456"},
                    {"subject": "STAT", "course": "400", "crn": "34567"},
                ]
            },
            headers=self._auth_header(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("at most", response.get_json()["error"])

    def test_schedule_upload_returns_async_job(self):
        with patch(
            "app.routes.schedules.schedules_controller.create_pdf_import_job",
            return_value={"job_id": "job-1", "job_type": "pdf_schedule_import", "status": "queued"},
        ):
            response = self.client.post(
                "/api/schedules/",
                data={"pdf": (io.BytesIO(b"x" * 16), "schedule.pdf")},
                headers=self._auth_header(),
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["job_id"], "job-1")

    def test_manual_course_add_returns_async_job(self):
        with patch(
            "app.routes.schedules.schedules_controller.create_crn_import_job",
            return_value={"job_id": "job-2", "job_type": "crn_schedule_import", "status": "queued"},
        ):
            response = self.client.post(
                "/api/schedules/courses?term=fall&year=2026",
                json={"courses": [{"subject": "CS", "course": "101", "crn": "12345"}]},
                headers=self._auth_header(),
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["job_id"], "job-2")

    def test_schedule_job_status_route_returns_404_for_other_user(self):
        with patch("app.routes.schedules.schedules_controller.get_job_status_for_user", return_value=None):
            response = self.client.get("/api/schedules/jobs/job-404", headers=self._auth_header())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Job not found")

    def test_schedule_job_status_route_returns_job_payload(self):
        with patch(
            "app.routes.schedules.schedules_controller.get_job_status_for_user",
            return_value={"job_id": "job-3", "status": "processing", "job_type": "crn_schedule_import"},
        ):
            response = self.client.get("/api/schedules/jobs/job-3", headers=self._auth_header())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "processing")


class BackendServiceTestCase(unittest.TestCase):
    def test_kick_member_checks_requester_and_target_separately(self):
        fake_cursor = _FakeCursor(fetchone_values=[("admin",), ("owner",)])

        @contextmanager
        def fake_get_cursor():
            yield fake_cursor

        with patch("app.routes.groups.groups_service.get_cursor", fake_get_cursor):
            with self.assertRaises(PermissionError):
                groups_service.kick_member("admin-user", "owner-user", "12")

        self.assertEqual(len(fake_cursor.calls), 2)
        self.assertEqual(fake_cursor.calls[0][1], ("12", "admin-user"))
        self.assertEqual(fake_cursor.calls[1][1], ("12", "owner-user"))


class BackendAuthValidationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = ec.generate_private_key(ec.SECP256R1())
        cls.public_key = cls.private_key.public_key()

    def setUp(self):
        self.config_patcher = patch.multiple(
            Config,
            SUPABASE_JWT_ISSUER="http://127.0.0.1:54321/auth/v1",
            SUPABASE_JWT_AUDIENCE="authenticated",
        )
        self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()

    def _encode_token(self, issuer=None, audience=None):
        payload = {
            "sub": "user-1",
            "iss": issuer or Config.SUPABASE_JWT_ISSUER,
            "aud": audience or Config.SUPABASE_JWT_AUDIENCE,
            "exp": 4102444800,
            "iat": 1704067200,
        }
        return jwt.encode(payload, self.private_key, algorithm="ES256")

    def test_verify_supabase_jwt_rejects_wrong_issuer(self):
        token = self._encode_token(issuer="http://malicious.example/auth/v1")

        with patch("app.utils.auth._get_jwks_client", return_value=_DummyJwksClient(self.public_key)):
            with self.assertRaises(InvalidTokenError):
                verify_supabase_jwt(token)

    def test_verify_supabase_jwt_rejects_wrong_audience(self):
        token = self._encode_token(audience="unexpected-audience")

        with patch("app.utils.auth._get_jwks_client", return_value=_DummyJwksClient(self.public_key)):
            with self.assertRaises(InvalidTokenError):
                verify_supabase_jwt(token)


class BackendConfigValidationTestCase(unittest.TestCase):
    def test_create_app_fails_fast_when_frontend_origin_missing(self):
        with patch.multiple(
            Config,
            FRONTEND_ORIGIN=None,
            SUPABASE_URL="http://127.0.0.1:54321",
            SUPABASE_SECRET_KEY="sb_secret_test",
            SUPABASE_JWT_ISSUER="http://127.0.0.1:54321/auth/v1",
            SUPABASE_JWT_AUDIENCE="authenticated",
            SUPABASE_HTTP_TIMEOUT_SECONDS=20.0,
            UIUC_API_TIMEOUT_SECONDS=5.0,
            MAX_IMAGE_UPLOAD_BYTES=16,
            MAX_PDF_UPLOAD_BYTES=32,
            MAX_MANUAL_COURSES_PER_REQUEST=2,
            DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres",
            DB_SSLMODE="disable",
            LOG_OPTIONS_REQUESTS=False,
            SUPABASE_SCHEDULE_PDF_BUCKET="schedule-pdfs",
            SUPABASE_SCHEDULE_PDF_PREFIX="schedule-imports",
            REDIS_URL="redis://localhost:6379/0",
            REDIS_JOB_LEASE_SECONDS=60,
            REDIS_JOB_HEARTBEAT_SECONDS=20,
            REDIS_JOB_MAX_ATTEMPTS=3,
            REDIS_JOB_RETRY_BASE_DELAY_SECONDS=5,
            REDIS_JOB_RESULT_TTL_SECONDS=86400,
            REDIS_JOB_POLL_INTERVAL_SECONDS=0.01,
            JWKS_URL="http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        ):
            with self.assertRaises(RuntimeError):
                create_app()


if __name__ == "__main__":
    unittest.main()
