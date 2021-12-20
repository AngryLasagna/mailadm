import deltachat
from deltachat import account_hookimpl, run_cmdline
from mailadm.db import DB
from mailadm.commands import add_user, add_token, list_tokens
import os

class AdmBot:
    def __init__(self, db):
        self.db = db
        with self.db.read_connection() as conn:
            config = conn.config()
            self.admingrpid = config.admingrpid

    @account_hookimpl
    def ac_incoming_message(self, command: deltachat.Message):
        print("process_incoming message:", command)
        command.create_chat()
        if not self.check_privileges(command):
            command.chat.send_text("Sorry, I only take commands from the admin group.")

        if command.text.strip() == "/help":
            text = ("/add-token name expiry prefix token maxuse"
                    "/add-user addr password token"
                    "/list-tokens")
            command.chat.send_text(text)

        elif command.text.strip() == "/add-token":
            arguments = command.text.split(" ")
            text = add_token(arguments[0], arguments[1], arguments[2], arguments[3], arguments[4])
            command.chat.send_text(text)

        elif command.text.strip() == "/add-user":
            arguments = command.text.split(" ")
            text = add_user(arguments[0], arguments[1], arguments[2])
            command.chat.send_text(text)

        elif command.text.strip() == "/list-tokens":
            command.chat.send_text(list_tokens())

    def check_privileges(self, command):
        """
        Checks whether the incoming message was in the admin group.
        """
        if command.chat.is_group() and self.admingrpid == command.chat.id:
            if command.chat.is_protected() and command.chat.is_encrypted() and int(command.chat.num_contacts) >= 2:
                if command.message.get_sender_contact() in command.chat.get_contacts():
                    return True
                else:
                    print("%s is not allowed to give commands to mailadm." % (command.message.get_sender_contact(),))
            else:
                print("admin chat is broken. Group ID:" + self.admingrpid)
                raise Exception
        else:
            # reply "This command needs to be sent to the admin group"
            return False


def main(db, argv=None):
    run_cmdline(argv=argv, account_plugins=[AdmBot(db)])


if __name__ == "__main__":
    db = DB(os.getenv("MAILADM_DB"))
    main(db)
