"use strict";

// The Blog page: a list of posts, and one post at #blog/<id>.

const Blog = (() => {
  const { $, el, fill, api } = CA;
  let posts = [];

  function longDate(iso) {
    const d = new Date(`${iso}T00:00:00`);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  }

  function renderIndex() {
    fill($("post-list"), posts.map((p, i) => el("li", {}, el("a", { class: "post-card", href: `#blog/${p.id}` },
      el("span", { class: "post-no", text: `Note ${String(i + 1).padStart(2, "0")}` }),
      el("h2", { text: p.title }),
      el("p", { text: p.summary }),
      el("span", { class: "post-meta", text: `${longDate(p.date)} · ${p.author} · ${p.minutes} min read` })))));
  }

  function show(id) {
    const post = posts.find((p) => p.id === id);
    $("blog-index").hidden = Boolean(post);
    $("post").hidden = !post;
    window.scrollTo({ top: 0 });
    if (!post) return;
    const body = el("div", { class: "post-body" });
    body.innerHTML = post.html; // rendered by Clarchy from its own posts, with all text HTML-escaped
    fill($("post"),
      el("a", { class: "back-link", href: "#blog", text: "← All posts" }),
      el("p", { class: "eyebrow", text: longDate(post.date) }),
      el("h1", { class: "post-title", text: post.title }),
      el("p", { class: "post-byline" }, el("a", { href: "#about", text: post.author }),
        post.role ? `, ${post.role}` : "", ` · ${post.minutes} min read`),
      body,
      el("div", { class: "post-foot" },
        el("a", { class: "btn btn-primary", href: "#plan", text: "Try it with your brief" }),
        el("a", { class: "btn btn-ghost", href: "#blog", text: "More posts" })));
  }

  async function init() {
    try { posts = await api.blog(); } catch { posts = []; }
    renderIndex();
  }

  return { init, show };
})();
