from drf_yasg.inspectors import SwaggerAutoSchema

class BearerAuthAutoSchema(SwaggerAutoSchema):
    def get_security(self):
        return [{'Bearer': []}]
