import os


def register_context(app):
    @app.context_processor
    def inject_school():
        return {
            "school_name": os.getenv("SCHOOL_NAME"),
            "school_phone": os.getenv("SCHOOL_PHONE"),
            "school_email": os.getenv("SCHOOL_EMAIL_GENERAL"),
            "school_web_address": os.getenv("SCHOOL_WEB_ADDRESS"),
        }
