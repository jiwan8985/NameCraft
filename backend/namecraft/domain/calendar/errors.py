from namecraft.errors import AppError


class CalendarInputError(AppError):
    status_code = 422
    code = "calendar_input_invalid"


class OutOfSupportedRange(AppError):
    status_code = 422
    code = "out_of_supported_range"


class EphemerisUnavailable(AppError):
    status_code = 503
    code = "ephemeris_unavailable"
