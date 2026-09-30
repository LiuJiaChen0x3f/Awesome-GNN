/* Only **bold** is interpreted. Every other character remains a text node. */
((root, factory) => {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MethodMarkdown = api;
})(globalThis, () => {
  'use strict';
  function tokens(value) {
    const text = String(value || ''), result = [];
    const pattern = /\*\*([^*\n]+)\*\*/g;
    let start = 0;
    for (const match of text.matchAll(pattern)) {
      if (match.index > start) result.push({text:text.slice(start, match.index), bold:false});
      result.push({text:match[1], bold:true});
      start = match.index + match[0].length;
    }
    if (start < text.length) result.push({text:text.slice(start), bold:false});
    return result;
  }
  function render(document, value) {
    const span = document.createElement('span');
    span.className = 'method-content';
    for (const token of tokens(value)) {
      if (token.bold) {
        const strong = document.createElement('strong');
        strong.textContent = token.text;
        span.append(strong);
      } else span.append(document.createTextNode(token.text));
    }
    return span;
  }
  return {tokens, render};
});
