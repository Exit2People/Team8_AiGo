import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AI GO",
    short_name: "AI GO",
    description: "몇 가지만 누르면 오늘 가기 좋은 곳과 가는 길을 알려 드려요.",
    start_url: "/",
    display: "standalone",
    lang: "ko",
    background_color: "#F6F3EE",
    theme_color: "#E8E4DD",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
