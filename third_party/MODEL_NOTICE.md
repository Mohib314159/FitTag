# Model attribution

This experimental container downloads Depth Anything V2 Small indoor metric
weights, converted to ONNX by Kornia. The model is not authored or trained by
FitTag. The Small model is released under Apache License 2.0; the larger model
licenses differ and those models are not distributed here.

Authors: Lihe Yang, Bingyi Kang, Zilong Huang, Xiaogang Xu, Jiashi Feng,
Hengshuang Zhao. Research: **Depth Anything V2**, arXiv:2406.09414.

- Original model: https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small
- Authors' code: https://github.com/DepthAnything/Depth-Anything-V2
- Kornia export: https://huggingface.co/kornia/depth-anything
- Pinned revision: `86f40563e7e87a0839be758988aa804930409a61`
- SHA-256: `50dbcac7a6d667e365a3ceffdf51cc497aa5e06b6d2c1d5824c252640fbf5bf3`

The export is used as downloaded; no fine-tuning or modification of its weights
was performed. FitTag adds image preprocessing, floor/geometry checks and product
behavior. A copy of Apache License 2.0 accompanies this notice.
