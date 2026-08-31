# src/core/exceptions.py
"""Custom exceptions"""

class ClawRoyaleError(Exception):
    pass

class ConfigurationError(ClawRoyaleError):
    pass

class VersionMismatchError(ClawRoyaleError):
    pass

class AgentDeadError(ClawRoyaleError):
    pass

class ResumeTargetDeadError(ClawRoyaleError):
    pass

class AuthenticationError(ClawRoyaleError):
    pass

class NotSelectedError(ClawRoyaleError):
    pass

class AgentTokenRequiredError(ClawRoyaleError):
    pass