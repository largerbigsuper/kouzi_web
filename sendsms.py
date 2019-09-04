#!/usr/bin/env python
# coding=utf-8

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest


def sendAddAuthCodeSms(username, tel, code, count):
    client = AcsClient('LTAI2D5XlcASSsE5',
                       'iWZlAtwSbgNeQ1Qbry1ZDekqmgL6QA', 'default')

    request = CommonRequest()
    request.set_accept_format('json')
    request.set_domain('dysmsapi.aliyuncs.com')
    request.set_method('POST')
    request.set_protocol_type('https')
    request.set_version('2017-05-25')
    request.set_action_name('SendSms')
    # 短信接收手机号
    request.add_query_param('PhoneNumbers', tel)
    # 短信签名名称
    request.add_query_param('SignName', '防撸宝')
    # 短信模板ID
    request.add_query_param('TemplateCode', 'SMS_169641265')

    request.add_query_param('TemplateParam',
                            "{\"username\":\""+str(username) +
                            "\",\"code\":\""+str(code) +
                            "\",\"count\":\""+str(count) +
                            "\"}")

    response = client.do_action(request)
    print(str(response, encoding='utf-8'))
