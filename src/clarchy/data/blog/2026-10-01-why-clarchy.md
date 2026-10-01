---
title: Why architecture needs a drawing, not a chat answer
date: 2026-10-01
author: Namrata Bhatia
role: Founder
summary: Requirements live in documents, decisions live in people's heads, and costs show up months later. Clarchy turns a brief into a drawing you can question, price and compare across clouds.
---
Every cloud project starts the same way. Someone writes a requirements document, an architect reads it, and a few days later a diagram appears. Between the two, dozens of decisions are made: which compute model, which database, how releases ship, what happens to data after seven years. Most of those decisions are never written down, so nobody can check them later.

Asking a chatbot is faster, but it doesn't fix the problem. You get a confident paragraph that names services, with no way to see which sentence of your brief led to which choice, what it will cost over three years, or what it would look like on another cloud.

## What Clarchy does differently

Clarchy reads the brief, typed or as a Word, PDF or Excel file, and produces an architecture you can inspect:

- **Every component says why it is there**, and quotes the sentence of your brief that asked for it. Anything Clarchy had to assume is listed, along with questions to confirm, and you can answer them and plan again.
- **The design is cloud-neutral first.** It is written as capabilities, such as a message queue, an agent runtime or archive storage, and then drawn on AWS, Azure, Google Cloud and open source, each in its own look. Comparing clouds is one click, not a second project.
- **Diagrams are drawn by code, not by a model.** The same design always produces the same drawing, so a review can focus on the decisions.
- **Costs are worked out, not guessed.** Each service is priced from list prices, for one month, six months, one year and three years, with and without commitments. AWS prices come straight from the AWS Price List API and are refreshed every week.
- **Build and run are part of the design.** Source control, CI, releases, infrastructure as code, access governance, audit trails, backups and retention are drawn alongside the app, because that is where most of the real work, and most of the risk, sits.

## Who it is for

Clarchy is for architects who want a first draft they can defend, for teams comparing clouds before they commit, for educators who want students to see why a design looks the way it does, and for anyone who has to explain a cloud bill to a finance team.

It is not a replacement for an architect. It is the drawing board: the place where a brief becomes something concrete enough to argue about.

Try it with your own brief on the [Plan page](#plan), or start from one of the [reference examples](#examples).
