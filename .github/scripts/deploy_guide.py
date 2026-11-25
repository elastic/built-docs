#!/usr/bin/env python3
"""Mirror built-docs html/ to s3://<bucket>/guide/.

Reads `git diff -z --name-status --no-renames <base> HEAD -- html/` from --diff-file, uploads added
and changed files from the working tree, and deletes removed ones. A full sync is a diff from git's
empty tree plus --full, which also deletes bucket keys that html/ does not contain.
PUT and DELETE are idempotent, so a rerun converges.
"""
import argparse
import json
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor

PREFIX = "guide/"
HTML_DIR = "html/"
# Terraform owns this object (not_found_page_path); html/ does not contain it.
PROTECTED_KEYS = {"guide/404.html"}
CACHE_CONTROL = "public, max-age=300"

# What the live site serves (parity check on elastic/docs-eng-team#1267).
CONTENT_TYPES = {
    ".kibana": "application/octet-stream",
    ".console": "application/octet-stream",
    ".sense": "application/octet-stream",
    ".woff2": "application/octet-stream",
    ".yaml": "application/octet-stream",
    ".map": "application/octet-stream",
    ".woff": "application/font-woff",
    ".js": "application/javascript; charset=utf-8",
    ".xml": "text/xml; charset=utf-8",
}


def key(path):
    return PREFIX + path[len(HTML_DIR):]


def headers(path):
    ext = os.path.splitext(path)[1].lower()
    content_type = CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
    return {"ContentType": content_type, "CacheControl": CACHE_CONTROL}


def plan_diff(tokens):
    """Tokens of `git diff -z --name-status --no-renames` (status NUL path NUL ...) -> (uploads, deletes).

    With -z, paths are never quoted. Five real files start with a literal quote.
    """
    if len(tokens) % 2:
        raise ValueError("diff -z output must be status/path pairs")
    uploads, deletes = [], []
    for status, path in zip(tokens[::2], tokens[1::2]):
        if status == "D":
            deletes.append(path)
        elif status in ("A", "M", "T"):
            uploads.append(path)
        else:
            raise ValueError(f"unexpected diff status {status!r} for {path!r}")
    return uploads, deletes


def extras(upload_paths, remote_keys):
    """Tree paths of bucket keys under guide/ that the tree does not contain (full sync only)."""
    wanted = {key(p) for p in upload_paths}
    return sorted(
        HTML_DIR + k[len(PREFIX):] for k in remote_keys
        if k.startswith(PREFIX) and k not in wanted and k not in PROTECTED_KEYS
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("GUIDE_BUCKET", "elastic-guide-website-prod"))
    p.add_argument("--diff-file", required=True)
    p.add_argument("--full", action="store_true", help="the diff is from the empty tree: also delete bucket extras")
    args = p.parse_args()

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", config=Config(max_pool_connections=128, retries={"max_attempts": 10, "mode": "adaptive"}))

    with open(args.diff_file, "rb") as f:
        uploads, deletes = plan_diff([t.decode("utf-8") for t in f.read().split(b"\0") if t])
    if args.full:
        pages = s3.get_paginator("list_objects_v2").paginate(Bucket=args.bucket, Prefix=PREFIX)
        deletes = extras(uploads, (o["Key"] for page in pages for o in page.get("Contents", [])))

    def put(path):
        with open(path, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            s3.put_object(Bucket=args.bucket, Key=key(path), Body=f, **headers(path))
        return size

    with ThreadPoolExecutor(max_workers=64) as pool:
        total = sum(pool.map(put, uploads))  # raises on the first failed PUT

    keys = [key(d) for d in deletes]
    for i in range(0, len(keys), 1000):
        resp = s3.delete_objects(Bucket=args.bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]], "Quiet": True})
        if resp.get("Errors"):
            raise SystemExit(f"delete failed: {resp['Errors'][:3]}")

    print(json.dumps({"uploaded": len(uploads), "bytes": total, "deleted": len(keys)}))


if __name__ == "__main__":
    main()
