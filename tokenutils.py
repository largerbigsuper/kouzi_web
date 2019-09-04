import uuid


def getTokenByUserId(userId):
    name = 'kouzi_admin_'
    namespace = uuid.NAMESPACE_URL
    return uuid.uuid3(namespace, name+userId)
