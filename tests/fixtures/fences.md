# Fence interactions

```markdown
- inside a plain fence
> - inside a quoted line of a fence
```

> ```markdown
> - inside a fence opened in a blockquote
> ```
>
> - reported: quote list after the fence closed

Four backticks keep a three-backtick line literal:

````markdown
```
- reported? no, still inside the four-backtick fence
```
````

- reported: after the four-backtick fence

Tildes do not close backtick fences:

~~~markdown
``` 
- still inside the tilde fence
~~~
