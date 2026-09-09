def repair_mojibake(value):
    ### Repair text that was incorrectly decoded as Latin-1
    ### after originally being encoded as UTF-8.
    ###
    ### Return the original value when the transformation is not
    ### applicable, preventing valid Unicode text from being modified.
    if not value:
        return value

    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value

    return repaired