"use strict";

// The Blog: a list of posts at /blog/ and each post on its own page (#blog and
// #blog/<id> on a single-file build). Both come drawn with the page (site.py); this draws a
// post shown without reloading, the same way.

const Blog = (() => {
  const { $, el, fill, api } = CA;
  let posts = null;

  function longDate(iso) {
    const d = new Date(`${iso}T00:00:00`);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  }

  function show(id) {
    const post = (posts || []).find((p) => p.id === id);
    if (!post) { CA.go(CA.href("blog"), { replace: true }); return; }
    const crumb = document.querySelector("#page-post [data-crumb]");
    if (crumb) crumb.textContent = post.title;
    const article = $("post");
    if (article.dataset.id === id) return;
    article.dataset.id = id;
    const body = el("div", { class: "post-body" });
    body.innerHTML = post.html; // rendered by Clarchy from its own posts, with all text HTML-escaped
    const about = CA.ROUTING === "path" ? `${CA.href("about")}#author` : CA.href("about");
    fill(article,
      el("p", { class: "post-date", text: longDate(post.date) }),
      el("h1", { class: "post-title", text: post.title }),
      el("p", { class: "post-byline" }, el("a", { href: about, text: post.author }),
        post.role ? `, ${post.role}` : "", ` · ${post.minutes} min read`),
      body,
      el("p", { class: "post-author", text: `${post.author} is the founder of Clarchy.` }),
      el("div", { class: "post-foot" },
        el("a", { class: "btn btn-primary", href: CA.href("plan"), text: "Try it with your brief" }),
        el("a", { class: "btn btn-ghost", href: CA.href("blog"), text: "More posts" })));
  }

  async function init() {
    if (posts) return;
    try { posts = await api.blog(); } catch { posts = []; }
    // A post's own page arrives with the post drawn: note which, so it isn't drawn twice.
    const article = $("post");
    const shown = location.pathname.match(/^\/blog\/([^/]+)\/$/);
    if (article && shown && article.childElementCount) article.dataset.id = shown[1];
  }

  return { init, show };
})();
