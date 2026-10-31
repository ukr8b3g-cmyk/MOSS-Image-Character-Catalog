"""Audited caption rules; preserve historical generation prompts and real tails."""

import re

REV='2026-10-31-caption-v1'

OLD_FRAME='Keep the entire head, all ears if present, tail tip if present, and all feet completely visible inside the frame.'

NEW_FRAME='Keep the entire character visible within the frame, with space around the silhouette.'

HAIR={
 'ponytail':'hair gathered and tied at the back of the head',
 'side ponytail':'hair gathered and tied on one side of the head',
 'high ponytail':'hair gathered and tied high at the back of the head',
 'low ponytail':'hair gathered and tied low at the back of the head',
 'high side ponytail':'hair gathered and tied high on one side of the head',
 'low side ponytail':'hair gathered and tied low on one side of the head',
 'short ponytail':'hair gathered into a short tied section at the back of the head',
 'braided ponytail':'hair gathered into a tied and braided section at the back of the head',
 'folded ponytail':'hair gathered, tied and folded into a loop at the back of the head',
 'front ponytail':'hair gathered into a tied section hanging in front',
 'split ponytail':'hair tied together at the back of the head and split into two hanging sections',
 'wide ponytail':'hair gathered into a wide tied section at the back of the head',
 'drill ponytail':'hair gathered into a tied section shaped in a spiral curl',
 'twintails':'hair divided into two tied sections on opposite sides of the head',
 'low twintails':'hair divided into two low tied sections on opposite sides of the head',
 'short twintails':'hair divided into two short tied sections on opposite sides of the head',
 'uneven twintails':'hair divided into two tied side sections of unequal length',
 'braided twintails':'hair divided into two braided and tied side sections',
 'pigtails':'hair divided into two tied sections on opposite sides of the head',
}

def tokens(text):
 if 'Appearance: ' not in text:return []
 return [s.strip() for s in text.split('Appearance: ',1)[1].split('. ',1)[0].rstrip('.').split(',') if s.strip()]

def repair_caption(text,character=True):
 if not character:return text,[]
 reasons=[];new=text
 # Retain human conditioning by default. Correct only an explicit contradiction
 # in the supplied appearance, rather than inferring species from ears or tails.
 if {'android','robot'} & {t.casefold() for t in tokens(text)}:
  new,n=re.subn(r'\b(female|male) human character\b',r'\1 character',new)
  new,m=re.subn(r'(?<!non-)\bhuman character\b','character',new)
  if n+m:reasons.append('remove_human_android_robot_contradiction')
 if OLD_FRAME in new:new=new.replace(OLD_FRAME,NEW_FRAME);reasons.append('neutral_full_body_framing')
 if 'Appearance: ' in new:
  head,tail=new.split('Appearance: ',1)
  match=re.match(r'(.*?)(\. |\.$|$)',tail,re.S)
  appearance,ending=match.group(1),tail[match.end(1):]
  tags=[s.strip() for s in appearance.split(',') if s.strip()]
  rewritten=[]
  for tag in tags:
   replacement=HAIR.get(tag.casefold(),tag)
   if replacement!=tag:reasons.append('explicit_hair_description')
   if replacement.casefold() not in {s.casefold() for s in rewritten}:rewritten.append(replacement)
   else:reasons.append('exact_duplicate_appearance')
  new=head+'Appearance: '+', '.join(rewritten)+ending
 return new,sorted(set(reasons))

def flags(r,effective):
 if r['kind']!='character':return []
 result=[];tags=[s.lower().strip() for s in r.get('copy_tags','').split(',')]
 app=tokens(effective)
 if not app:result.append('appearance_not_supplied')
 if ('1girl' in tags or '1boy' in tags) and 'no humans' in tags:result.append('source_human_creature_conflict')
 if '1girl' in tags and '1boy' in tags:result.append('source_multiple_gender_tags')
 colors=r'(?:black|brown|light brown|dark brown|blonde|white|grey|gray|red|pink|blue|aqua|purple|green|orange|yellow|silver|golden)'
 for part in ['hair','eyes']:
  found=[s for s in app if re.fullmatch(colors+' '+part,s,re.I)]
  mixed=any(s in [t.lower() for t in app] for s in (['two-tone hair','multicolored hair','gradient hair','streaked hair','colored inner hair'] if part=='hair' else ['heterochromia','multicolored eyes']))
  if len(set(found))>1 and not mixed:result.append('source_multiple_'+part+'_colors')
 if any('braid' in s.lower() for s in app) and any(s.lower() in HAIR and 'braided' not in s.lower() for s in app):result.append('source_multiple_tied_hairstyles')
 return result

def ui_changes(html,js):
 marker='<label><span data-i18n="copyTagsLabel">'
 assert html.count(marker)==1
 block='<section id="reuse-generation-section" hidden><p class="muted" data-i18n="promptRevisionHelp"></p><label><span data-i18n="reuseGenerationLabel"></span><textarea id="reuse-generation-prompt" readonly></textarea></label><button id="copy-reuse-generation" type="button" data-i18n="copyReuseGeneration"></button></section>'
 html=html.replace(marker,block+marker)
 at='  const panelFields='
 assert js.count(at)==1
 translations="""  Object.assign(messages.ja,{reuseGenerationLabel:'再生成用プロンプト（修正版）',copyReuseGeneration:'再生成用をコピー',promptRevisionHelp:'2026-10-31に文章を整理。画像は再生成していません。保存ワークフロー・元タグは当時の記録です。修正による画質改善やキャラクターの正確性は未検証です。',openWorkflow:'当時の生成ワークフローを開く'});
  Object.assign(messages.en,{reuseGenerationLabel:'Revised prompt for a new generation',copyReuseGeneration:'Copy revised generation prompt',promptRevisionHelp:'Prompt wording revised on 2026-10-31. Images were not regenerated. Saved workflows and original tags are historical records. Improved output quality and character accuracy have not been verified.',openWorkflow:'Open original generation workflow'});
"""
 js=js.replace(at,translations+at)
 js=js.replace("openWorkflow:'保存JSONを開く'","openWorkflow:'当時の生成ワークフローを開く'").replace("openWorkflow:'Open workflow JSON'","openWorkflow:'Open original generation workflow'")
 needle="$('detail-tags').value=record.copy_tags;"
 assert js.count(needle)==1
 js=js.replace(needle,needle+"$('reuse-generation-section').hidden=!record.reuse_generation_prompt;$('reuse-generation-prompt').value=record.reuse_generation_prompt||'';")
 needle="  $('copy-prompt').onclick="
 assert js.count(needle)==1
 js=js.replace(needle,"  $('copy-reuse-generation').onclick=()=>copyText(current.reuse_generation_prompt).catch(error=>notice(error.message));\n"+needle)
 return html,js
