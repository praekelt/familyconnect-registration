from celery.task import Task
from celery.utils.log import get_task_logger

from familyconnect_registration import utils


logger = get_task_logger(__name__)


class AddUniqueIDToIdentity(Task):
    def run(self, identity, unique_id, write_to, **kwargs):
        """
        identity:     the identity to receive the payload.
        unique_id:    the unique_id to add to the identity
        write_to:     the key to write the unique_id to
        """
        details = utils.get_identity(identity)
        if "details" in details:
            # not a 404
            payload = {
                "details": details["details"]
            }
            payload["details"][write_to] = unique_id
            utils.patch_identity(identity, payload)
            return "Identity <%s> now has <%s> of <%s>" % (
                identity, write_to, str(unique_id))
        else:
            return "Identity <%s> not found" % (identity,)

add_unique_id_to_identity = AddUniqueIDToIdentity()
