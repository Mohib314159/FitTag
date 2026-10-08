# Deploy the full app on Render

FitTag is one Docker web service: FastAPI serves the PWA and the existing OpenCV engine on the same origin. There is no separate frontend build, database, model download or API key.

## Render setup

Push this branch to your GitHub repository, then create a Render Blueprint from `render.yaml`, or create a **Web Service** with **Docker** as the runtime and `Dockerfile` as the Dockerfile path. Leave Docker Command blank; the image starts Uvicorn on `0.0.0.0` and `$PORT` (default `10000`). Set the health check path to `/health`.

The Blueprint selects the free plan; a paid instance avoids free-service sleep for demonstrations. Confirm current availability and costs in Render before changing the plan. Render terminates HTTPS for the public service URL, which is necessary for PWA installation and the service worker. No environment secrets are required. `.env.example` lists the port and thread controls.

Official references: [Docker on Render](https://render.com/docs/docker), [web service ports](https://render.com/docs/web-services), [free-service limitations](https://render.com/docs/free).

## Resource limits

- One Uvicorn worker, one OpenCV thread, and one measurement at a time. Concurrent measurement attempts get a clear 429 response and retry guidance.
- Uploads: 12 MB / 25 megapixels. EXIF orientation is applied, metadata is discarded, and the analysis image is reduced to a maximum 1800-pixel long edge.
- Reference fallback rectification uses 1 mm per pixel to reduce its working size. Hardware capture works directly at the reduced photo resolution.
- Processed photo outputs are capped at 40 files and become inaccessible after one hour. Expired files are cleaned up on subsequent measurements. Render's temporary filesystem is sufficient; restarts remove prior outputs. The original upload is not persisted by the app.
- Saving stores measurement values in the user's browser, not photos. Clearing saved measurements is available in the app. Browser storage clearing also removes them.
- No optional rembg, Torch, CLIP or vision-provider packages are installed. The user chooses the garment type.

This configuration targets a small instance, but actual peak memory must still be observed on Render with representative phones and fallback photographs. Container limits and real device capture cannot be proven by a Windows local run alone. Avoid multiple workers on a constrained instance.

## Local container check

```sh
docker build -t fittag .
docker run --rm -p 8000:10000 -e PORT=10000 fittag
```

Open http://127.0.0.1:8000. For Python development without Docker, use the README commands. `requirements-render.txt` pins the exercised package versions, using the headless OpenCV variant in deployment.

## Check after deployment

1. Open `/health`, then the app root on an iPhone/Android. Try the synthetic example; tap a measurement and change units.
2. Choose a photo, tap Measure, and check the detected button and every measurement line. Confirm the overlay before saving. Verify that missing buttons, a cropped image and offline mode produce useful recovery states.
3. Install from Safari's Share menu or Android's browser install control. Reopen in standalone mode. After an initial online visit, the capture guide and synthetic example should load offline; a new measurement must request connectivity.
4. Check memory and response times in Render. A sleeping free instance can delay the first upload; the app allows up to two minutes and preserves the selected photo on timeout. Cancelling stops the browser request, though server-side analysis already started may finish.

The GitHub Pages copy under `docs/` is a static demo. It does not run Python or measure uploads. Use the Render HTTPS URL for the full experience.
