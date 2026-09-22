"""Deprecated MCX execution calibration writer.

Provider-scoped schema-2 calibration is controlled by the certification
workflow. This historical schema-1 helper must never overwrite calibration
authority.
"""

_MESSAGE = "DEPRECATED_MCX_EXEC_CONFIG_WRITER: schema-1 calibration writes are disabled"

raise SystemExit(_MESSAGE)
