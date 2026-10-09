---
name: case-optional-fields
description: Count CSV rows when a user requests a row count.
license: Apache-2.0
compatibility: Requires Python 3 and local read access to the requested CSV.
metadata:
  author: trial-fixture
  version: "1.0"
---
Read the requested CSV with a CSV parser. Exclude the header from the data-row count and report that count.
