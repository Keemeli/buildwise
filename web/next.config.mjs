/** @type {import('next').NextConfig} */
const nextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // The result page used to live at /build. Old links keep working; the query
  // (?budget=…&game=…) is passed through to the new page.
  redirects() {
    return [{ source: "/build", destination: "/suggestion", permanent: true }];
  },
};

export default nextConfig;
