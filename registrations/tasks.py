import datetime
import six  # for Python 2 and 3 string type compatibility
import requests
import json

from django.conf import settings
from celery.task import Task
from celery.utils.log import get_task_logger

from .models import Registration, SubscriptionRequest
from familyconnect_registration import utils


logger = get_task_logger(__name__)


def is_valid_date(date):
    try:
        datetime.datetime.strptime(date, "%Y%m%d")
        return True
    except:
        return False


def is_valid_uuid(id):
    return len(id) == 36 and id[14] == '4' and id[19] in ['a', 'b', '8', '9']


def is_valid_lang(lang):
    return lang in ["eng_UG", "cgg_UG", "xog_UG", "lug_UG"]


def is_valid_msg_type(msg_type):
    return msg_type in ["text"]  # currently text only


def is_valid_msg_receiver(msg_receiver):
    return msg_receiver in ["head_of_household", "mother_to_be",
                            "family_member", "trusted_friend"]


def is_valid_loss_reason(loss_reason):
    return loss_reason in ['miscarriage', 'stillborn', 'baby_died']


def is_valid_name(name):
    return isinstance(name, six.string_types)  # TODO reject non-letters


def is_valid_id_type(id_type):
    return id_type in ["ugandan_id", "other"]


def is_valid_id_no(id_no):
    return isinstance(id_no, six.string_types)  # TODO proper id validation


class ValidateRegistration(Task):
    """ Task to validate a registration model entry's registration
    data.
    """
    name = "familyconnect_registration.registrations.tasks.\
    validate_registration"

    def check_field_values(self, fields, registration_data):
        failures = []
        for field in fields:
            if field in ["hoh_id", "receiver_id", "operator_id"]:
                if not is_valid_uuid(registration_data[field]):
                    failures.append(field)
            if field == "language":
                if not is_valid_lang(registration_data[field]):
                    failures.append(field)
            if field == "msg_type":
                if not is_valid_msg_type(registration_data[field]):
                    failures.append(field)
            if field in ["last_period_date", "baby_dob", "mama_dob"]:
                if not is_valid_date(registration_data[field]):
                    failures.append(field)
                else:
                    # Check that if mama_dob is provided, the ID type is other
                    if (field == "mama_dob" and
                       registration_data["mama_id_type"] != "other"):
                        failures.append("mama_dob requires id_type other")
                    # Check last_period_date is in the past and < 42 weeks ago
                    if field == "last_period_date":
                        preg_weeks = utils.calc_pregnancy_week_lmp(
                            utils.get_today(), registration_data[field])
                        if not (2 <= preg_weeks <= 42):
                            failures.append("last_period_date out of range")
            if field == "msg_receiver":
                if not is_valid_msg_receiver(registration_data[field]):
                    failures.append(field)
            if field == "loss_reason":
                if not is_valid_loss_reason(registration_data[field]):
                    failures.append(field)
            if field in ["hoh_name", "hoh_surname", "mama_name",
                         "mama_surname"]:
                if not is_valid_name(registration_data[field]):
                    failures.append(field)
            if field == "mama_id_type":
                if not is_valid_id_type(registration_data[field]):
                    failures.append(field)
            if field == "mama_id_no":
                if not is_valid_id_no(registration_data[field]):
                    failures.append(field)
                # Check that if ID no is provided, the ID type ugandan_id
                if not registration_data["mama_id_type"] == "ugandan_id":
                    failures.append("mama_id_no requires id_type ugandan_id")
        return failures

    def validate(self, registration):
        """ Validates that all the required info is provided for a
        prebirth registration.
        """
        data_fields = registration.data.keys()
        fields_general = ["hoh_id", "receiver_id", "operator_id", "language",
                          "msg_type"]
        fields_prebirth = ["last_period_date", "msg_receiver"]
        fields_loss = ["loss_reason"]
        fields_hw_id = ["hoh_name", "hoh_surname", "mama_name", "mama_surname",
                        "mama_id_type", "mama_id_no"]
        fields_hw_dob = ["hoh_name", "hoh_surname", "mama_name",
                         "mama_surname", "mama_id_type", "mama_dob"]

        # Perhaps the below should rather be hardcoded to save a tiny bit of
        # processing time for each registration
        hw_pre_id = list(set(fields_general) | set(fields_prebirth) |
                         set(fields_hw_id))
        hw_pre_dob = list(set(fields_general) | set(fields_prebirth) |
                          set(fields_hw_dob))
        pbl_pre = list(set(fields_general) | set(fields_prebirth))
        pbl_loss = list(set(fields_general) | set(fields_loss))

        # Check if mother_id is a valid UUID
        if not is_valid_uuid(registration.mother_id):
            registration.data["invalid_fields"] = "Invalid UUID mother_id"
            registration.save()
            return False

        if "msg_receiver" in registration.data.keys():
            # Reject registrations where the hoh is the receiver but the
            # hoh_id and receiver_id differs
            if (registration.data["msg_receiver"] == "head_of_household" and
               registration.data["hoh_id"] != registration.data[
                    "receiver_id"]):
                registration.data["invalid_fields"] = "hoh_id should be " \
                    "the same as receiver_id"
                registration.save()
                return False
            # Reject registrations where the mother is the receiver but the
            # mother_id and receiver_id differs
            elif (registration.data["msg_receiver"] == "mother_to_be" and
                  registration.mother_id != registration.data["receiver_id"]):
                registration.data["invalid_fields"] = "mother_id should be " \
                    "the same as receiver_id"
                registration.save()
                return False
            # Reject registrations where the family / friend is the receiver
            # but the receiver_id is the same as the mother_id or hoh_id
            elif (registration.data["msg_receiver"] in
                  ["family_member", "trusted_friend"] and (
                    registration.data["receiver_id"] ==
                    registration.data["hoh_id"] or (
                    registration.data["receiver_id"] ==
                    registration.mother_id))):
                registration.data["invalid_fields"] = "receiver_id should" \
                    "differ from hoh_id and mother_id"
                registration.save()
                return False

        # HW registration, prebirth, id
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_id).issubset(data_fields)):  # ignore extra data
            invalid_fields = self.check_field_values(
                hw_pre_id, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "hw_pre_id"
                registration.data["preg_week"] = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        # HW registration, prebirth, dob
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_dob).issubset(data_fields)):
            invalid_fields = self.check_field_values(
                hw_pre_dob, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "hw_pre_dob"
                registration.data["preg_week"] = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        # Public registration (currently only prebirth)
        elif (registration.stage == "prebirth" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_pre).issubset(data_fields)):
            invalid_fields = self.check_field_values(
                pbl_pre, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "pbl_pre"
                registration.data["preg_week"] = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        # Loss registration
        elif (registration.stage == "loss" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_loss).issubset(data_fields)):
            invalid_fields = self.check_field_values(
                pbl_loss, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "pbl_loss"
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        else:
            registration.data[
                "invalid_fields"] = "Invalid combination of fields"
            registration.save()
            return False

    def create_subscriptionrequests(self, registration):
        """ Create SubscriptionRequest(s) based on the
        validated registration.
        """

        if 'preg_week' in registration.data:
            weeks = registration.data["preg_week"]
        else:
            weeks = registration.data["baby_age"]

        short_name = utils.get_messageset_short_name(
            registration.data["msg_receiver"], registration.stage,
            registration.source.authority
        )

        msgset_id, msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(
                short_name, weeks)

        mother_sub = {
            "contact": registration.mother_id,
            "messageset": msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": registration.data["language"],
            "schedule": msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        return "SubscriptionRequest created"

    def run(self, registration_id, **kwargs):
        """ Sets the registration's validated field to True if
        validation is successful.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up the registration")
        registration = Registration.objects.get(id=registration_id)
        reg_validates = self.validate(registration)

        validation_string = "Validation completed - "
        if reg_validates:
            validation_string += "Success"
            self.create_subscriptionrequests(registration)
        else:
            validation_string += "Failure"

        return validation_string

validate_registration = ValidateRegistration()


class DeliverHook(Task):
    def run(self, target, payload, instance=None, hook=None, **kwargs):
        """
        target:     the url to receive the payload.
        payload:    a python primitive data structure
        instance:   a possibly null "trigger" instance
        hook:       the defining Hook object
        """
        requests.post(
            url=target,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % settings.HOOK_AUTH_TOKEN
            }
        )

deliver_hook_wrapper = DeliverHook.delay
