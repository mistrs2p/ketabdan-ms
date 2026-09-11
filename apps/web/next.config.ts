import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  // Production container runtime (Task 5.11; docs/01 §12): emit a
  // self-contained server in .next/standalone (server.js + only the
  // traced files). Local development (`next dev`) and local production
  // builds (`next build && next start`) are unaffected — standalone is
  // purely an additional output the Docker image copies.
  output: "standalone",
  // The i18n message catalogs are loaded through a dynamic import with a
  // template literal (i18n/request.ts), which output file tracing cannot
  // see statically — include them explicitly so the standalone server
  // ships them. (apps/web/Dockerfile also copies messages/ as a belt to
  // this suspenders.)
  outputFileTracingIncludes: {
    "/(.*)?": ["./messages/**"],
  },
};

export default withNextIntl(nextConfig);
