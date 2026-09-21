import { useEffect } from "react";
import { SITE } from "./site";

const TITLE = SITE.siteTitle;

/**
 * One title and one description per view. A single-page app otherwise ships
 * the same <title> and <meta name="description"> to every route, so a shared
 * link to one intersection previews as the home page and search engines index
 * one page. The canonical link follows the view for the same reason.
 */
export default function usePageMeta({ title, description }) {
  useEffect(() => {
    document.title = title ? `${title} | ${TITLE}` : TITLE;

    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    if (description) meta.setAttribute("content", description);

    let link = document.querySelector('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("rel", "canonical");
      document.head.appendChild(link);
    }
    const { origin, pathname, search } = window.location;
    link.setAttribute("href", origin + pathname + search);
  }, [title, description]);
}
