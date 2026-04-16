# cdn.strinova.gg

Static assets served from [cdn.strinova.gg](https://cdn.strinova.gg), used by [Stringify](https://stringify.gg).

This repo exists so the main Stringify repo doesn't have to ship these files. Splitting them out keeps the app repo small and shortens deploy times — asset changes don't trigger an app rebuild, and app changes don't re-upload the CDN.

## Contents

All assets live under [assets/](assets/). Each subdirectory groups a category of resource (agents, maps, `news` mirrors for the in-app news feed, id_cards, pings, loadouts, etc.) referenced by the Stringify app at runtime via `https://cdn.strinova.gg/assets/<path>`.

## How uploads work

On every push to `main` that touches [assets/](assets/), [.github/workflows/upload-r2.yml](.github/workflows/upload-r2.yml) runs [.github/scripts/upload_r2.py](.github/scripts/upload_r2.py), which syncs [assets/](assets/) to the Cloudflare R2 bucket backing the CDN. The script compares local MD5s against remote ETags and only uploads changed files, so re-runs are cheap.

Manual re-runs are available via the **Run workflow** button on the Actions tab (`workflow_dispatch`).

## Adding assets

1. Drop files into the appropriate subdirectory under [assets/](assets/).
2. Commit and push to `main`.
3. The workflow will pick up the changes and upload them to R2.

Files become available at `https://cdn.strinova.gg/assets/<path-relative-to-assets>`.
