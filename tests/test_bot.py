import time
import pytest
import deltachat
from deltachat.capi import lib as dclib


TIMEOUT = 90


@pytest.mark.timeout(TIMEOUT)
class TestAdminGroup:
    def test_help(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/help")
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("/add-user addr password token")

    def test_list_tokens(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        command = admingroup.send_text("/list-tokens")
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("Existing tokens:")
        assert reply.quote == command

    def test_check_privileges(self, admingroup):
        direct = admingroup.botadmin.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        num_msgs = len(direct.get_messages())
        while len(direct.get_messages()) == num_msgs:  # this sometimes never completes
            time.sleep(0.1)
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."


@pytest.mark.timeout(TIMEOUT)
class TestSupportGroup:
    def test_support_group_relaying(self, admingroup, supportuser):
        class SupportGroupUserPlugin:
            def __init__(self, account, supportuser):
                self.account = account
                self.account.add_account_plugin(deltachat.events.FFIEventLogger(self.account))
                self.supportuser = supportuser

            @deltachat.account_hookimpl
            def ac_incoming_message(self, message: deltachat.Message):
                message.create_chat()

                assert len(message.chat.get_contacts()) == 2
                assert message.override_sender_name == self.supportuser.get_config("addr")

                if message.text == "Can I ask you a support question?":
                    message.chat.send_text("I hope the user can't read this")
                    print("sent secret message")
                    reply = deltachat.Message.new_empty(self.account, "text")
                    reply.set_text("Yes of course you can ask us :)")
                    reply.quote = message
                    message.chat.send_msg(reply)
                    print("sent public message")
                else:
                    print("botadmin received:", message.text)

        supportchat = supportuser.create_chat(admingroup.admbot.get_config("addr"))
        question = "Can I ask you a support question?"
        supportchat.send_text(question)
        admin = admingroup.botadmin
        admin.add_account_plugin(SupportGroupUserPlugin(admin, supportuser))
        while len(admin.get_chats()) < 2:
            time.sleep(0.1)
        # AcceptChatPlugin will send 2 messages to the support group now
        support_group_name = supportuser.get_config("addr") + " support group"
        support_group_name = " " + support_group_name  # workaround for deltachat-core-rust #3650
        for chat in admin.get_chats():
            print(chat.get_name())
        supportgroup = next(filter(lambda chat: chat.get_name() == support_group_name,
                                   admin.get_chats()))
        while len(supportchat.get_messages()) < 2:
            time.sleep(0.1)
        botreply = supportchat.get_messages()[1]
        assert botreply.text == "Yes of course you can ask us :)"
        supportchat.send_text("Okay, I will think of something :)")
        while len(supportgroup.get_messages()) < 4:
            time.sleep(0.1)
        assert "I hope the user can't read this" not in \
               [msg.text for msg in supportchat.get_messages()]

    def test_invite_bot_to_group(self, admingroup, supportuser):
        botcontact = supportuser.create_contact(admingroup.admbot.get_config("addr"))
        false_group = supportuser.create_group_chat("invite bot", [botcontact])
        num_msgs = len(false_group.get_messages())
        false_group.send_text("Welcome, bot!")
        while len(false_group.get_messages()) < num_msgs + 3:
            time.sleep(0.1)
        assert len(false_group.get_contacts()) == 1
        sorry_message = "Sorry, you can not contact me in a group chat. Please use a 1:1 chat."
        assert false_group.get_messages()[num_msgs + 1].text == sorry_message
        assert botcontact.get_profile_image()

    def test_bot_receives_system_message(self, admingroup):
        def get_group_chats(account):
            group_chats = []
            for chat in ac.get_chats():
                if chat.is_group():
                    group_chats.append(chat)
            return group_chats

        ac = admingroup.admbot
        num_chats = len(get_group_chats(ac))
        # put system message in admbot's INBOX
        dev_msg = deltachat.Message.new_empty(ac, "text")
        dev_msg.set_text("This shouldn't create a support group")
        dclib.dc_add_device_msg(ac._dc_context, bytes("test_device_msg", "ascii"), dev_msg._dc_msg)
        # assert that admbot didn't create a support group
        assert num_chats == len(get_group_chats(ac))
