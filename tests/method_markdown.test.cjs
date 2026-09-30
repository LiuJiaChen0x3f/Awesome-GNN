const test = require('node:test');
const assert = require('node:assert/strict');
const {tokens, render} = require('../site/method-markdown.js');

test('bold emphasis preserves surrounding prose and newlines', () => {
  assert.deepEqual(tokens('采用**模块A**对齐。\n再以**目标B**训练。'), [
    {text:'采用',bold:false},{text:'模块A',bold:true},{text:'对齐。\n再以',bold:false},
    {text:'目标B',bold:true},{text:'训练。',bold:false}
  ]);
});
test('HTML and links are written as text, never interpreted', () => {
  const tags = [];
  const document = {
    createElement(tag) { tags.push(tag); return {tag,children:[],append(x){this.children.push(x);}}; },
    createTextNode(text) { return {text}; }
  };
  const out = render(document, '<img src=x onerror=alert(1)>**<script>x</script>**[a](javascript:x)');
  assert.deepEqual(tags,['span','strong']);
  assert.equal(out.children[0].text,'<img src=x onerror=alert(1)>');
  assert.equal(out.children[1].textContent,'<script>x</script>');
  assert.equal(out.children[2].text,'[a](javascript:x)');
});
test('plain legacy summaries and unmatched stars remain visible text', () => {
  assert.deepEqual(tokens('旧总结**未闭合'),[{text:'旧总结**未闭合',bold:false}]);
});
