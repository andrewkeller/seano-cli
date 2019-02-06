"""
pyseano/constants.py
Shared constants used by seano
"""

SEANO_DEFAULT_EDITOR = 'vim'

SEANO_CONFIG_FILE = 'seano-config.yaml'
SEANO_CONFIG_TEMPLATE = '---\n'

SEANO_DB_SUBDIR = 'v1'
SEANO_TEMPLATE_EXTENSION = '.yaml'
SEANO_TEMPLATE_CONTENTS = '''---
releases: Name or names of releases in which this change was released.  May be a string or a list of strings.

risk: One of low, medium, high; risk level here does not factor in deployment tricks to minimize risk.

tickets:
- URL to JIRA/Redmine ticket

min-supported-os: "version number"  # Supported OS fields are sticky; use only when this change changes them.
max-supported-os: "version number"  # Values should be in quotes to force them to be strings.

milestones-short:
  en-US:
  - Short description of a big milestone to be pointed out prominently in internal notes archives

downgrade-break-short: Short reason you created a Downgrade Compatibility Break, in past tense

public-short:
  en-US:
  - Explain, in short bullets, what changed.
  - Target audience is our public customers.
  - This text usually comes from Marketing.

internal-short:
  en-US:
  - Explain, in short bullets, what changed.
  - Target audience is CE Employees.
  - This text usually comes from developers.

technical:
  en-US: |
    Explain, in as many words as it takes, what changed.  Target audience is Ops, and your future self.

    Second paragraph goes here

testing:
  en-US: |
    Explain, in as many words as it takes, how to test this change.  Target audience is QA, and your future self.

    Second paragraph goes here
'''
