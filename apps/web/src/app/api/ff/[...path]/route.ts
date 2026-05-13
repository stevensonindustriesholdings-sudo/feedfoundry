import { NextRequest, NextResponse } from "next/server";
import { getServerConfig } from "@/lib/server/config";
import { isDevAccountCreditsMockEnabled, mockAccountCreditsJson } from "@/lib/server/dev-mock-credits";
import { forwardToFeedFoundry } from "@/lib/server/feedfoundry-upstream";

const ORG_CLIENT_HEADER = "x-feedfoundry-org-id";

/** Build upstream path from catch-all segments */
function upstreamPath(segments: string[]): string {
  return `/${segments.join("/")}`;
}

function isAllowed(method: string, segments: string[]): boolean {
  const p = segments.join("/");

  if (method === "GET") {
    if (p === "health" || p === "ready") return true;
    if (p === "v1/account" || p === "v1/account/usage" || p === "v1/account/credits") return true;
    if (p === "v1/jobs") return true;
    if (/^v1\/jobs\/[^/]+$/.test(p)) return true;
    if (/^v1\/jobs\/[^/]+\/outputs$/.test(p)) return true;
    if (/^v1\/jobs\/[^/]+\/outputs\/catalog$/.test(p)) return true;
    if (/^v1\/manifests\/[^/]+\/[^/]+\.json$/.test(p)) return true;
    return false;
  }
  if (method === "POST") {
    if (p === "v1/uploads/presign") return true;
    if (p === "v1/uploads/complete") return true;
    if (p === "v1/jobs") return true;
    if (/^v1\/jobs\/[^/]+\/cancel$/.test(p)) return true;
    return false;
  }
  return false;
}

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  try {
    return await handle(request, ctx, "GET");
  } catch (e) {
    return NextResponse.json(
      { detail: "proxy_handler_error", message: (e as Error).message },
      { status: 502 },
    );
  }
}

export async function POST(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  try {
    return await handle(request, ctx, "POST");
  } catch (e) {
    return NextResponse.json(
      { detail: "proxy_handler_error", message: (e as Error).message },
      { status: 502 },
    );
  }
}

async function handle(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
  method: "GET" | "POST",
) {
  try {
    getServerConfig();
  } catch (e) {
    return NextResponse.json(
      { error: "server_misconfigured", message: (e as Error).message },
      { status: 500 },
    );
  }

  const { path: pathSegments = [] } = await ctx.params;
  if (!isAllowed(method, pathSegments)) {
    return NextResponse.json({ error: "path_not_allowed" }, { status: 404 });
  }

  const path = upstreamPath(pathSegments);
  const orgHeader = request.headers.get(ORG_CLIENT_HEADER);

  if (
    method === "GET" &&
    isDevAccountCreditsMockEnabled() &&
    (path === "/v1/account" || path === "/v1/account/usage" || path === "/v1/account/credits")
  ) {
    return new NextResponse(mockAccountCreditsJson(), {
      status: 200,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }

  const { defaultOrgId } = getServerConfig();
  const orgId = orgHeader?.trim() || defaultOrgId;

  let body: string | undefined;
  const headers: Record<string, string> = {};
  if (method === "POST") {
    const ct = request.headers.get("content-type");
    if (ct) headers["Content-Type"] = ct;
    body = await request.text();
  }

  let upstream: Response;
  try {
    upstream = await forwardToFeedFoundry(path, {
      method,
      body,
      orgId,
      headers: Object.keys(headers).length ? headers : undefined,
    });
  } catch (e) {
    return NextResponse.json(
      { detail: "proxy_upstream_unreachable", message: (e as Error).message },
      { status: 502 },
    );
  }

  const resHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) resHeaders.set("content-type", ct);

  const text = await upstream.text();

  if (!upstream.ok) {
    try {
      JSON.parse(text);
      return new NextResponse(text, {
        status: upstream.status,
        headers: resHeaders,
      });
    } catch {
      const wrapped = JSON.stringify({
        detail: "upstream_non_json_body",
        message: text.slice(0, 2000),
      });
      const errHeaders = new Headers();
      errHeaders.set("content-type", "application/json; charset=utf-8");
      return new NextResponse(wrapped, {
        status: upstream.status,
        headers: errHeaders,
      });
    }
  }

  return new NextResponse(text, {
    status: upstream.status,
    headers: resHeaders,
  });
}
