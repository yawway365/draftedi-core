class MissingSpecError(ValueError):
    """
    Raised when spec-dependent validation is attempted without a provider.

    Example message:
        "validate_edi() requires a spec_provider for full X12 validation.
         Supply an X12SpecProvider implementation, or install draftedi-specs."
    Inherits from ValueError for backward-compatible except ValueError handling. (ref: DL-006)
    """

    pass
