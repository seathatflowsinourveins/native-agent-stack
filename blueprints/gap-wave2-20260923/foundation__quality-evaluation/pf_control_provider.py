"""Constant-prediction control: always answers candidate 0 without any model call.

It shows the vars-based assertion can fail: its pass count must equal the
number of cases whose label is 0, not 30.
"""


def call_api(prompt, options, context):
    return {"output": "pred=0"}
