"""IronPanel web UI split into domain modules (v19.10.26).

Every submodule registers its routes on the single shared ``web`` blueprint,
so all existing ``url_for('web.*')`` endpoints, templates and links keep
working unchanged. The blueprint is intentionally NOT renamed.
"""
from flask import Blueprint

web_bp = Blueprint('web', __name__)

from . import common  # noqa: E402,F401  (app-wide hooks/context processor)
from . import auth  # noqa: E402,F401
from . import dashboard  # noqa: E402,F401
from . import users  # noqa: E402,F401
from . import resellers  # noqa: E402,F401
from . import subscriptions  # noqa: E402,F401
from . import nodes  # noqa: E402,F401
from . import network  # noqa: E402,F401
from . import billing  # noqa: E402,F401
from . import ops  # noqa: E402,F401
from . import system  # noqa: E402,F401
from . import bots  # noqa: E402,F401
from . import cards  # noqa: E402,F401
