/* 25 real browser conversations against the OFFLINE explicit-engine fixture.
   No route mocks. This validates state/UI/catalog wiring, not DeepSeek quality. */
const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.BAG_TEST_URL||'http://127.0.0.1:8145');await page.waitForFunction(()=>goods.length===64);let group=null;const results=[];
for(const c of JSON.parse(fs.readFileSync('tests/acceptance_cases.json','utf8'))){
 if(c.group!==group){await page.evaluate(()=>fresh());group=c.group}
 if(c.target_ids)await page.evaluate(ids=>attachProducts(ids),c.target_ids);
 await page.locator('#input').fill(c.text);await page.locator('#send').click();await page.waitForFunction(()=>!busy);
 const state=await page.evaluate(()=>({conditions,last:messages.filter(m=>m.role==='assistant').at(-1)}));assert.ok(!state.last.error,JSON.stringify(state));
 for(const [k,v] of Object.entries(c.expected_conditions))assert.deepEqual(state.conditions[k],v,`${c.id}: ${k}`);
 for(const k of c.absent_conditions)assert.ok(!(k in state.conditions),`${c.id}: still has ${k}`);
 if(c.expected_primary_count!==null)assert.equal(state.last.primary_ids.length,c.expected_primary_count,`${c.id}: count`);
 const bot=page.locator('#messages .msg.bot').last();const displayed=await bot.locator('.product-story>h4').allTextContents();const ids=state.last.primary_ids.length?[...state.last.primary_ids,...state.last.backup_ids]:state.last.ids;
 const names=await page.evaluate(ids=>ids.map(i=>good(i).name),ids);assert.equal(displayed.length,names.length);displayed.forEach((text,i)=>assert.ok(text.includes(names[i])));
 if(c.id>=21)assert.equal(await bot.locator('.question').count(),0);
 if(c.id===7||c.id===14){await bot.scrollIntoViewIfNeeded();await page.screenshot({path:`/tmp/bag-v10-case-${c.id}.png`,fullPage:true})}
 results.push({id:c.id,status:'passed',conditions:state.conditions,primary_ids:state.last.primary_ids});
}
await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.evaluate(()=>fresh());await page.screenshot({path:'/tmp/bag-v10-mobile.png'});
assert.deepEqual(errors,[]);fs.writeFileSync('/tmp/baodongni-25-browser-results.json',JSON.stringify({scope:'offline-browser-real-requests-no-model',results},null,2));await browser.close();console.log('PASS 25/25 browser conversations: explicit conditions, removals, result counts, exact text/card pairing, no analysis follow-up, mobile layout; no model invoked');})().catch(e=>{console.error(e);process.exit(1)});
