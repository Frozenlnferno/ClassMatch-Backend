from flask import Blueprint

bp = Blueprint("schedule/", __name__)

from .controller import *   # registers routes
