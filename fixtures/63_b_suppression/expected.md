# Suppression

<!-- no-markdown-bullets: off reason="legacy template kept verbatim" -->
- suppressed: inside a closed region
* suppressed too
<!-- no-markdown-bullets: on reason="resume checking" -->

reported: after the region closed

<!-- no-markdown-bullets: off -->
reported: a directive without a reason does not take effect

<!-- no-markdown-bullets: off reason="" -->
reported: an empty reason does not take effect either

```markdown
<!-- no-markdown-bullets: off reason="inside a fence" -->
- reported: a marker inside a fence is inert, so this is a real bullet
```

<!-- no-markdown-bullets: off reason="intentionally left open" -->
- suppressed: inside the unclosed region
