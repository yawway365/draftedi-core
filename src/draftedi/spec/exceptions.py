class MissingSpecError(ValueError):
    """
    Exception for spec-dependent validation attempted without spec data.

    No draftedi function raises it: validate_edi() and X12Validator report a
    missing spec with is_valid=None instead. It is exported for API
    compatibility. Inherits from ValueError.
    """

    pass
