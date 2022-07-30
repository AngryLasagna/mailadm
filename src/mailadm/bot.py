import sys
import sqlite3
import deltachat
from deltachat import account_hookimpl
from mailadm.db import DB, get_db_path
from mailadm.commands import add_user, add_token, list_tokens
import os
from threading import Event


class SetupPlugin:
    def __init__(self, admingrpid):
        self.member_added = Event()
        self.admingrpid = admingrpid
        self.message_sent = Event()

    @account_hookimpl
    def ac_member_added(self, chat: deltachat.Chat, contact, actor, message):
        assert chat.num_contacts() == 2
        if chat.id == self.admingrpid:
            self.member_added.set()

    @account_hookimpl
    def ac_message_delivered(self, message: deltachat.Message):
        if not message.is_system_message():
            self.message_sent.set()


class AdmBot:
    def __init__(self, db: DB, account: deltachat.Account):
        self.db = db
        self.account = account
        with self.db.read_connection() as conn:
            config = conn.config
            self.admingrpid = config.admingrpid

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        print("process_incoming message:", message.text)
        if not self.check_privileges(message):
            message.create_chat()
            message.chat.send_text("Sorry, I only take commands from the admin group.")
            return

        if message.text.strip() == "/help":
            text = ("/add-token name expiry prefix token maxuse"
                    "/add-user addr password token"
                    "/list-tokens")
            message.chat.send_text(text)

        elif message.text.strip() == "/add-token":
            arguments = message.text.split(" ")
            text = add_token(self.db, arguments[0], arguments[1], arguments[2], arguments[3],
                             arguments[4])
            message.chat.send_text(text)

        elif message.text.strip() == "/add-user":
            arguments = message.text.split(" ")
            text = add_user(self.db, arguments[0], arguments[1], arguments[2])
            message.chat.send_text(text)

        elif message.text.strip() == "/list-tokens":
            message.chat.send_text(list_tokens(self.db))

    def check_privileges(self, command: deltachat.Message):
        """
        Checks whether the incoming message was in the admin group.
        """
        if command.chat.is_group() and self.admingrpid == command.chat.id:
            if command.chat.is_protected() \
                    and command.chat.is_encrypted() \
                    and int(command.chat.num_contacts) >= 2:
                if command.get_sender_contact() in command.chat.get_contacts():
                    return True
                else:
                    print("%s is not allowed to give commands to mailadm." %
                          (command.get_sender_contact(),))
            else:
                print("admin chat is broken. Try `mailadm setup-bot`. Group ID:", self.admingrpid)
                raise ValueError
        else:
            return False


def get_admbot_db_path():
    db_path = os.environ.get("ADMBOT_DB", "/mailadm/docker-data/admbot.db")
    try:
        sqlite3.connect(db_path)
    except sqlite3.OperationalError:
        raise RuntimeError("admbot.db not found: ADMBOT_DB not set")
    return db_path


def main(mailadm_db):
    ac = deltachat.Account(get_admbot_db_path())
    try:
        ac.run_account(account_plugins=[AdmBot(mailadm_db, ac)], show_ffi=True)
    except AssertionError as e:
        if "you must specify email and password once to configure this database/account" in str(e):
            raise Exception("please run mailadm setup-bot to configure the bot")
    ac.wait_shutdown()
    print("shutting down bot.", file=sys.stderr)


if __name__ == "__main__":
    mailadm_db = DB(get_db_path())
    main(mailadm_db)
