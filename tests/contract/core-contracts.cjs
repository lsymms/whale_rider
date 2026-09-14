"use strict";

// Standalone contract harness. It deliberately uses no application modules so the
// fixtures remain portable while the MVP service is being built.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../..");
const fixture=JSON.parse(fs.readFileSync(path.join(root,"tests/fixtures/contracts/core-contracts.json"),"utf8"));
function scaled(value,scale){
 const [whole,fraction=""]=String(value).split(".");
 return BigInt(whole+fraction.padEnd(scale,"0").slice(0,scale));
}
const money=value=>scaled(value,2);
// Quantity is fixed to four decimal places, price to cents, and multiplier is
// integral. The result is cents, with no binary floating point arithmetic.
const decimalCents=(quantity,price,multiplier="1")=>scaled(quantity,4)*scaled(price,2)*BigInt(multiplier)/10000n;
let passed=0;
function check(name,actual,expected){assert.equal(actual,expected,name);passed++;}

for(const test of fixture.alert_cases){
 const {rule,event}=test; let result="ignore";
 if(event.event_type!=="execution") result="ignore";
 else if(rule.template==="A01") result=money(event.quantity)>=money(rule.minimum_shares)&&decimalCents(event.quantity,event.price)>=money(rule.minimum_notional_usd)?"trigger":"ignore";
 else if(!event.multiplier_verified) result="block_unknown_multiplier";
 else result=money(event.quantity)>=money(rule.minimum_contracts)&&decimalCents(event.quantity,event.price,event.price_multiplier)>=money(rule.minimum_premium_usd)?"trigger":"ignore";
 check(test.name,result,test.expected);
}
for(const test of fixture.ocr_cases){
 if(test.row){
  const eligible=test.row.requires_review.length===0&&Boolean(test.row.reviewed_quantity||test.row.extracted_quantity);
  check(test.name,eligible,test.expected_commit_eligible);
 }else{
  const retained=test.existing_instrument_ids.filter(id=>!test.visible_instrument_ids.includes(id));
  check(test.name,JSON.stringify(retained),JSON.stringify(test.expected_retained_instrument_ids));
 }
}
const suggestion=JSON.parse(fs.readFileSync(path.join(root,"examples/suggestion.json"),"utf8"));
const allowedCandidates=new Set(suggestion.ai_contract.allowed_candidate_ids), evidence=new Set(suggestion.evidence_ids);
const knownNumbers=new Set(["50","24,000","24000","31,500","31500","27,000","27000","200","7,500","7500"]);
for(const test of fixture.suggestion_cases){
 const response=test.model;
 let result="accept";
 if(response.ranked_candidate_ids.some(id=>!allowedCandidates.has(id))) result="reject_candidate";
 else if(response.supporting_evidence_ids.some(id=>!evidence.has(id))) result="reject_evidence";
 else {
  const amounts=response.rationale.match(/\$?[\d,]+(?:\.\d+)?/g)||[];
  if(amounts.some(value=>!knownNumbers.has(value.replace("$","")))) result="reject_ungrounded_number";
 }
 check(test.name,result,test.expected);
}
console.log(`PASS: ${passed} core alert, OCR, and suggestion contract cases.`);
