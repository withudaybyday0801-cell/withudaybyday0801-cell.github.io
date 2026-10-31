/* Browser regression with controlled model replies; does not call DeepSeek. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[],requests=[];let failNext=false;
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/api/chat',async route=>{const r=route.request().postDataJSON();requests.push(r);if(failNext){failNext=false;return route.fulfill({status:503,json:{error:'测试临时中断'}})}
let reply={reply:'结论：【空包510g】。电脑隔层缓冲一般，日常通勤可用。',intent:r.action==='auto'?'analysis':r.action,conditions:r.conditions,ids:r.target_ids||[],product_texts:{},question:'',choices:[],suggestions:['换一款更轻的看看']};
if(r.start_selection)reply={...reply,intent:'recommend',reply:'好呀，先说说平时怎么用。',ids:[],question:'平时主要背去上课、上班，还是出门玩？',choices:['上课和校园日常','上班通勤','短途出行']};
else if(r.action==='recommend'||r.text.includes('上课'))reply={...reply,intent:'recommend',ids:[],primary_ids:[4,11],backup_ids:[8],product_texts:{4:'430g，浅蓝配色好搭。',11:'更适合短途出行。'}};
await route.fulfill({json:reply});});
const base=process.env.BAG_TEST_URL||'http://127.0.0.1:8142';await page.goto(base);await page.waitForFunction(()=>goods.length===22);
assert.equal(await page.locator('.featured .commerce-card').count(),4);
assert.equal(await page.locator('.data-disclosure').count(),1);
assert.match(await page.locator('.foot').innerText(),/模拟数据/);
assert.equal(await page.locator('[onclick="linkBox()"], [onclick="about()"]').count(),0);
assert.match(await page.locator('link[rel=icon]').getAttribute('href'),/a84991/);
assert.equal(new Set(await page.evaluate(()=>goods.map(p=>p.photo))).size,22);
// Both title and picture resolve to the matching internal product detail.
await page.locator('.featured .commerce-title').nth(1).click();assert.match(await page.locator('#title').innerText(),/骆驼/);assert.match(await page.locator('#body').innerText(),/296g/);assert.match(await page.locator('#body').innerText(),/用户评价/);assert.match(await page.locator('#body a[target=_blank]').getAttribute('href'),/^https:\/\/search.jd.com/);await page.getByRole('button',{name:'关闭',exact:true}).click();
// Repeated IDs and repeated clicks never add duplicate cart rows.
await page.evaluate(()=>{cartItems=[1,1,2,2];cart()});assert.equal(await page.locator('[name=cart-question]').count(),2);await page.locator('[name=cart-question]').first().check();await page.getByRole('button',{name:'带入聊天框提问'}).click();assert.equal(await page.locator('.attached-product').count(),1);
await page.locator('#input').fill('这款的主要缺点是什么');await page.locator('#send').click();await page.waitForFunction(()=>!busy);assert.equal(requests.at(-1).action,'analysis');assert.deepEqual(requests.at(-1).target_ids,[1]);assert.ok(await page.locator('.bot .text strong').count()>=1);assert.equal(await page.locator('.modebar button.active').count(),0);
// Multi-product custom question and actual parameter table.
await page.evaluate(()=>attachProducts([1,2]));await page.locator('#input').fill('哪个更适合带电脑');await page.locator('#send').click();await page.waitForFunction(()=>!busy);assert.equal(requests.at(-1).action,'compare');assert.deepEqual(requests.at(-1).target_ids,[1,2]);assert.match(await page.locator('.table-wrap').last().innerText(),/510g/);assert.doesNotMatch(await page.locator('.table-wrap').last().innerText(),/重量.*未显示/);assert.equal(await page.locator('.table-wrap').last().locator('[data-product]').count(),4);
// Select mode starts a consumer message and follow-up, then consumes its choice.
await page.locator('[data-mode=recommend]').click();await page.waitForFunction(()=>!busy);assert.equal(requests.at(-1).text,'请帮我推荐一款背包');assert.equal(requests.at(-1).start_selection,true);assert.equal(await page.locator('.modebar button.active').count(),0);assert.equal(await page.locator('.question-options').count(),1);
await page.locator('.question-options button').first().click();await page.waitForFunction(()=>!busy);assert.equal(await page.locator('.question-options').count(),0);assert.equal(requests.at(-1).text,'上课和校园日常');
assert.equal(await page.locator('.product-story').count()>0,true);await page.locator('.suggest [data-q]').last().click();await page.waitForFunction(()=>!busy);assert.equal(requests.at(-1).text,'换一款更轻的看看');
// Failure and retry preserve target selection and do not duplicate user message.
await page.evaluate(()=>attachProducts([2]));await page.locator('#input').fill('再说说缺点');failNext=true;await page.locator('#send').click();await page.waitForFunction(()=>!busy);await page.getByRole('button',{name:'重试这条消息'}).click();await page.waitForFunction(()=>!busy);assert.deepEqual(requests.at(-1).target_ids,[2]);assert.equal(await page.evaluate(()=>messages.filter(m=>m.role==='user'&&m.content==='再说说缺点').length),1);
// Persistence, history, clear, comparison picker and responsive layout.
await page.reload();await page.waitForFunction(()=>goods.length===22);assert.equal(await page.evaluate(()=>cartItems.length),2);assert.equal(await page.evaluate(()=>messages.length>0),true);
await page.locator('[data-mode=compare]').click();await page.locator('[name=cmp]').nth(1).check();await page.locator('[name=cmp]').nth(2).check();await page.locator('#overlay').getByRole('button',{name:'比较已选商品',exact:true}).click();await page.waitForFunction(()=>!busy);assert.equal(requests.at(-1).action,'compare');assert.equal(await page.locator('.modebar button.active').count(),0);
await page.locator('[data-mode=analysis]').click();assert.match(await page.locator('#title').innerText(),/分析/);await page.getByRole('button',{name:'关闭',exact:true}).click();assert.equal(await page.locator('.modebar button.active').count(),0);
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:'/tmp/bag-v9-mobile.png',fullPage:true});
await page.setViewportSize({width:1440,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:'/tmp/bag-v9-desktop.png',fullPage:true});
await page.locator('#input').fill('/clear');await page.locator('#send').click();assert.equal(await page.evaluate(()=>messages.length),0);await page.getByRole('button',{name:'历史',exact:true}).click();assert.equal(await page.locator('#body').innerText().then(x=>x.length>0),true);await page.getByRole('button',{name:'关闭',exact:true}).click();
await page.goto(base+'/?product=2');await page.waitForFunction(()=>goods.length===22);assert.match(await page.locator('#title').innerText(),/波斯丹顿/);assert.match(await page.locator('#body').innerText(),/510g/);
assert.deepEqual(errors,[]);await browser.close();console.log('PASS: homepage, details, links, cart dedup, attachment Q&A, comparison, selection follow-up, consumed choices, no sticky modes, suggestions, retry, persistence, clear, history, deep links, mobile/desktop, no JS errors');})().catch(e=>{console.error(e);process.exit(1)});
