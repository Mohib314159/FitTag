# Experimental MoGe-2 comparison

The unmerged buttonless audit uses Microsoft's MoGe-2 Small metric point-map
model. FitTag did not train these weights. The model is not bundled in the
serving Docker image or selected by the production app.

- Official source: https://github.com/microsoft/MoGe
- Inspected source commit: `74fbce054ebed49800de42d0ad0e83495065719a`
- Author export: https://huggingface.co/Ruicheng/moge-2-vits-normal-onnx
- Pinned revision: `e50ffda41565591092adea54c6ac83d6212e1e23`
- SHA-256: `24eacb5dc7a2c54c7bc98f7de085ffbed79ad006ea5b664c2c2cdc02ff3a52f0`

The small NumPy/SciPy projection adapter follows the authors' focal/shift and
metric-scale conventions. ONNX exports contain the forward pass only, so raw
affine points must not be mistaken for final measured metres. The upstream
MIT license is included as MOGE_LICENSE.txt. None of the model's general depth
benchmark claims establishes clothing-measurement accuracy.
