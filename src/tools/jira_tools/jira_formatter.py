
class JiraFormatter:
    @staticmethod
    def options(value):
        return {'value': value}

    @staticmethod
    def user(value):
        return {'name': value}

    @staticmethod
    def array(value):
        return [{'value': v for v in value}]

    @staticmethod
    def number(value):
        return value

    @staticmethod
    def string(value):
        return value

    @staticmethod
    def unavailable(value):
        return value

    @staticmethod
    def any(value):
        return value

    @staticmethod
    def project(value):
        return {'key': value}

    @staticmethod
    def version(value):
        return {'name': value}

    @staticmethod
    def datetime(value):
        # format must be: yyyy-MM-dd'T'HH:mm:ss.SSSZ
        return value

    @staticmethod
    def issue_type(value):
        return {'name': value}
