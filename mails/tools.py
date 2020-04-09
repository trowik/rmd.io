from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.utils.encoding import smart_bytes
from django.utils import timezone
from hashlib import sha1
import base64
import datetime
import logging
import os
import re


logger = logging.getLogger("mails")
host = re.sub("http(s)?://", "", settings.SITE_URL)


def get_delay_days_from_email_address(email_address):
    """Gets the delay days from an email address

    :param  email_address: delay email address
    :type   email_address: string
    :rtype: integer
    """
    try:
        match = re.findall(r"^(\d+)([dmw])", email_address)[0]
        multiplicator = settings.EMAIL_SUFFIX_TO_DAY[match[1]]
        delay = int(match[0]) * int(multiplicator)
        return delay
    except:
        raise Exception("Invalid delay")


def get_delay_addresses_from_recipients(recipients):
    """Gets the delay addresses from a set of recipients

    :param  recipients: list of recipients
    :type   recipients: list
    :rtype: list
    """
    delay_addresses = []
    for recipient in recipients:
        if re.search(r"^(\d+[dmw])", recipient["email"]):
            delay_addresses.append(recipient["email"])
    if delay_addresses:
        return delay_addresses
    else:
        raise Exception("Could not find a delay address")


def get_key_from_email_address(email_address):
    """Get the key of an email address

    :param  email_address: the email address with included key
    :type   email_address: string
    :rtype: string
    """
    try:
        return re.search(r"^\d+[dmw]\.([0-9a-z]{10})@", email_address).group(1)
    except AttributeError:
        return None


def send_registration_mail(recipient):
    """Sends an error mail to not registred users and logs it

    :param  recipient: the email address of the recipient
    :type   recipient: string
    """
    from mails.models import AddressLog

    try:
        AddressLog.objects.get(email=recipient, reason="NREG")
    except:
        tpl = get_template("mails/messages/not_registered_mail.txt")

        subject = "Register at %s!" % host
        content = tpl.render(
            {"recipient": recipient, "url": settings.SITE_URL, "host": host}
        )

        msg = EmailMessage(subject, content, settings.EMAIL_HOST_USER, [recipient])

        msg.send()

        log_entry = AddressLog(email=recipient, reason="NREG", attempt=1)
        log_entry.save()


def send_wrong_recipient_mail(recipient):
    """Sends an error mail to not registred users

    :param  recipient: the email address of the recipient
    :type   recipient: string
    """
    from mails.models import AddressLog

    try:
        AddressLog.objects.get(email=recipient)
    except:
        tpl = get_template("mails/messages/wrong_recipient_mail.txt")

        subject = "Your mail on %s was deleted!" % host
        content = tpl.render({"recipient": recipient, "host": host})
        msg = EmailMessage(subject, content, settings.EMAIL_HOST_USER, [recipient])

        msg.send()


def send_activation_mail(key, recipient):
    """Sends an activation mail for additional addresses

    :param  key:       the activation key
    :type   key:       string
    :param  recipient: the email address of the recipient
    :type   recipient: string
    """
    from mails.models import AddressLog

    subject = "Activate your address on %s" % host
    tpl = get_template("mails/messages/activation_mail.txt")
    content = tpl.render({"recipient": recipient, "key": key, "host": host})

    msg = EmailMessage(subject, content, settings.EMAIL_HOST_USER, [recipient])

    try:
        log_entry = AddressLog.objects.get(email=recipient, reason="SPAM")

        if log_entry.date < timezone.now() or log_entry.attempt > 5:
            logger.warning(
                "No registration email was sent. %s is blocked" % (recipient)
            )
            return

        else:

            log_entry.attempt += 1
            log_entry.date = timezone.now() + get_block_delay(log_entry.attempt)
            log_entry.save()

        msg.send()

    except:
        msg.send()

        log_entry = AddressLog(
            email=recipient, reason="SPAM", attempt=0, date=timezone.now()
        )
        log_entry.save()


def send_connection_mail(key, recipient, account):
    """Sends a mail which confirms the connection of
    an existing user to another existing account

    :param  key:       the activation key (urlsafe b64 of username)
    :type   key:       string
    :param  recipient: the email address of the recipient
    :type   recipient: string
    :param  account    the account which it should be connected to
    :type   account    mails.models.Account
    """
    from mails.models import AddressLog

    subject = "Confirm your address on %s" % host
    tpl = get_template("mails/messages/connection_mail.txt")
    content = tpl.render(
        {"recipient": recipient, "account_id": account.id, "key": key, "host": host}
    )

    msg = EmailMessage(subject, content, settings.EMAIL_HOST_USER, [recipient])

    try:
        log_entry = AddressLog.objects.get(email=recipient, reason="SPAM")

        if log_entry.date < timezone.now() or log_entry.attempt > 5:
            logger.warning("No connection email was sent. %s is blocked" % (recipient))
            return

        else:

            log_entry.attempt += 1
            log_entry.date = timezone.now() + get_block_delay(log_entry.attempt)
            log_entry.save()

        msg.send()

    except:
        msg.send()

        log_entry = AddressLog(
            email=recipient, reason="SPAM", attempt=0, date=timezone.now()
        )
        log_entry.save()


def get_block_delay(attempt):
    """Gets the block delay by attempt

    :param  attempt: the attempt to get the delay for
    :type   attempt: integer
    """
    return settings.BLOCK_DELAYS.get(attempt, datetime.timedelta(7))


def get_all_users_of_account(user):
    """Gets all users of the current users account

    :param  user: the user
    :type   user: models.User
    :rtype: list
    """
    return User.objects.filter(userprofile__account=user.get_account()).order_by(
        "-last_login"
    )


def calendar_clean_subject(subj):
    """Cleans the subject of a mail

    Removes common prefixes like Re, Fwd...

    :param  subj: the mails subject
    :type   subj: string
    :rtype: string
    """
    strip_re = "(%s)" % ")|(".join(settings.CALENDAR_STRIP_PREFIXES)
    after = re.sub(strip_re, "", subj)
    if after == subj:
        return after
    return calendar_clean_subject(after)


def create_additional_user(email, user):
    """Creates an additional user with the same password and identity

    :param  email:   the email address of the new user
    :type   email:   string
    :param  user:    the user which wants to create a new user
    :type   email:   django.contrib.auth.models.User
    """
    from mails.models import UserProfile, AddressLog

    new_user = User(
        email=email,
        username=base64.urlsafe_b64encode(sha1(smart_bytes(email)).digest())
        .decode("utf-8")
        .rstrip("="),
        date_joined=timezone.now(),
        password=user.password,
        is_active=False,
    )
    new_user.save()

    account = user.get_account()
    user_profile = UserProfile(user=new_user, account=account)

    user_profile.save()

    try:
        user_log_entry = AddressLog.objects.filter(email=user.email)
        user_log_entry.delete()
    except:
        pass

    key = base64.urlsafe_b64encode(new_user.username.encode("utf-8")).decode("utf-8")
    send_activation_mail(recipient=email, key=key)


def delete_log_entries(email):
    """Deletes all log entries of an email address

    :param email: the email which should be removed from log
    :type  email: string
    """
    from mails.models import AddressLog

    try:
        user_log_entry = AddressLog.objects.filter(email=email)
        user_log_entry.delete()
    except:
        pass


def generate_key():
    """Generates an unique user key

    :rtype: string
    """
    return base64.b32encode(os.urandom(7))[:10].lower().decode("utf-8")
