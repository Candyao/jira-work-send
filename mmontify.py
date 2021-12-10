#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor
import hug
executor = ThreadPoolExecutor(2)
from telegram import Bot
from telegram import ParseMode
import configparser
import json

conf=configparser.ConfigParser()
conf.read("config.ini",encoding="utf-8")


def get_bot():
    token=conf.get("COMMON","bot_token")
    bot = Bot(token=token)
    return bot

class JiraTask:
    def __init__(self, data):
        try:
            self.issueId = data['issue'].get('key', '')   # Issue ID
            self.issue_event_type_name = data.get('issue_event_type_name', '')  # Event type name
            self.status = data['issue']['fields']['status'].get('name', None)  # 任务状态
            self.assignee = data['issue']['fields']['assignee'].get('name', None)  # 经办人账号
            self.url = data['issue']['self']
            self.assigneename = data['issue']['fields']['assignee'].get('displayName', None)
            self.title = data['issue']['fields'].get('summary', None)  # 任务标题
            self.reporter = data['issue']['fields']['reporter'].get('displayName', None)  # 问题报告人账号
            self.created = data['issue']['fields'].get('created', None)  # 问题创建时间
            self.updated = data['issue']['fields'].get('updated', None)  # 问题更新时间
        except Exception as e:
            #raise e
            print(e)
            return

        try:
            self.fromString = data['changelog']['items'][0].get('fromString', None)
            self.toString = data['changelog']['items'][0].get('toString', None)
            self.field = data['changelog']['items'][0].get('field', None)
        except Exception as e:
            #raise e
            print(e)
            self.fromString = self.toString = None

    def check_jira_url(self):
        url_key=conf.options("JIRA")
        for var in url_key:
            jira_url=conf.get("JIRA",var)
            if jira_url in self.url:
                return jira_url
        return False

    def get_username(self,user):
        info=conf.get("USER",user)
        return info

    def _splice_mattermost_msg(self):
        JIRA_URL=self.check_jira_url()
        if JIRA_URL:
            url = f'{JIRA_URL}/browse/{self.issueId}'
        else:
            url = "None"

        try:  # 触发条件：工单被分配
            if self.issue_event_type_name == 'issue_created':
                msg = f'<b>工单提醒</b>\n{self.assigneename} 你好，{self.reporter} 新建的工单<a href="{url}">[{self.issueId} {self.title}]</a>已分配给你，请及时处理！'
            elif hasattr(self, 'fromString') and self.field == 'assignee' and self.fromString is None and self.toString is not None:
                msg = f'<b>工单提醒</b>\n{self.assigneename} 你好，{self.reporter} 新建的工单<a href="{url}">[{self.issueId} {self.title}]</a>已分配给你，请及时处理！'
            elif hasattr(self, 'fromString') and self.field == 'assignee' and self.fromString is not None and self.toString is not None:
                msg = f'<b>工单提醒</b>\n{self.assigneename} 你好，{self.reporter} 提交的工单<a href="{url}">[{self.issueId} {self.title}]</a>已流转给你，前序经办人是：{self.fromString}，请及时处理！'
            else:
                msg = None
        except Exception as e:
            print(e)
            msg = None
        return msg

    def send_mattermost(self):
        msg = self._splice_mattermost_msg()
        try:
            bot=get_bot()
            bot.send_message(chat_id=self.get_username(self.assignee), text=msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(e)
            return False


@hug.post()
def mmnotify(body):
    print(body)
    t = JiraTask(body)
    message = t._splice_mattermost_msg()
    try:
        if message is not None and message != '':
            executor.submit(t.send_mattermost)
            return {'code': 200, 'status': 'knowledge', 'jira_issue_status': t.status, 'message': '已执行发送信息：' + message}
        else:
            return {'code': -2, 'status': 'failed', 'jira_issue_status': t.status, 'message': 'message为空'}
    except Exception:
        return {'code': -1, 'status': 'failed', 'message': '参数不正确！'}

if __name__ == '__main__':
    hug.API(__name__).http.serve(port=8890)  #python api 端口
