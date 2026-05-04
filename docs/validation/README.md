# Cultivation type validation tool

This small application visualizes the cultivation types of three different source systems (agricultural policy information system `agis`, Suisse nutrient balance `naebi` and registry of plant protection products `psm`) in a manner where subject matter experts can verify/validate them.

To view it locally, run:

``` bash
cd docs/validation
python -m http.server
```

Use URL parameter `?system=agis` to set either `agis`, `naebi` or `psm` as the system of interest. 