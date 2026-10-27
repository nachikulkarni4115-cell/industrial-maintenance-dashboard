# Analytics & Predictive Maintenance (Stage 2+)

This directory holds reproducible scripts for downloading, preprocessing, and evaluating models on genuine public industrial datasets.

**NASA C-MAPSS** (turbofan engine degradation) is a common candidate.  
It must never be presented as measured electric-motor or pump data. Use it only in a clearly labelled separate analytics workflow.

Training and heavy preprocessing must be performed on a local machine or separate environment — not on the constrained EC2 instance.

No model is claimed as production-ready until evaluation metrics on held-out data are actually produced and documented.
