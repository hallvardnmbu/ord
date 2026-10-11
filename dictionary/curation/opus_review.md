# Opus review: what changed

Opus (low reasoning) reviewed the 953 approved words and the 427 unreviewed words in the Sonnet 30-40 band,
with the brief in `prompts/opus_review.md`. Verdicts are in `opus_review.json`.

- Your own yes-words are dropped only for your stated rules (dialect, technical, archaic, spelling, offensive).
  Where Opus called them common, dull or derived, your yes stands.
- Words only a model approved (Sonnet >= 40) are dropped for any Opus reason.
- 30-40 band words Opus kept are added (`picked_by: opus`).

To undo a drop, set the word to `[1, "ok"]` in `opus_review.json` and rerun `catalogue.py` + `export.mjs`.

## Your yes-words dropped (166)

**archaic** (18)
deild (bm), kvæve (bm), lend (bm), singott (nn), sjølvare (nn), skirsle (nn), stendig (bm), stinge (bm), tagne (bm), tauvre (nn), tendre (nn), trælke (nn), vandle (bm), veidn (bm), veum (bm), vinnskipelig (bm), åbyrgjast (nn), øksel (bm)

**dialect** (95)
andæres (nn), baus (nn), bibre (nn), bidlund (nn), brosten (nn), bærle (nn), børel (nn), draulen (nn), drette (nn), drulte (nn), drunt (nn), drøype (nn), dumbe (nn), fløygje (nn), gare (nn), gjednigen (nn), gjegne (nn), gjenegen (nn), gjøleleg (nn), gjølme (nn), gleine (nn), gleipe (nn), gnallande (nn), grøype (nn), gåig (nn), havang (nn), hortug (nn), huskeleg (nn), klabben (nn), kleise (bm), klessen (nn), klåte (bm), kodde (bm), kolke (nn), kolten (nn), kraklen (nn), krame (nn), kreiste (nn), kropne (nn), kverr (nn), kvetje (nn), ljoske (nn), nauteskap (nn), neitte (nn), nuve (nn), nyggje (nn), nøgge (nn), ormekte (nn), orvhendt (nn), radl (nn), skarken (nn), skat (bm), skirleitt (nn), skjekke (nn), skjelme (bm), skolle (nn), skrate (nn), skreide (nn), skrykke (nn), skrøkke (nn), skøyre (nn), sleinen (nn), slevje (nn), smålog (nn), smætte (nn), smøyeleg (nn), snippen (nn), spauke (nn), spjarre (nn), sterre (nn), stikte (nn), stivle (nn), stratt (nn), striple (nn), stropne (nn), stryllete (nn), styrven (nn), svalke (nn), svalle (nn), sveivle (nn), svipleg (nn), sykjast (nn), tilbrigde (nn), tistete (nn), traspe (nn), trumpen (nn), tryste (nn), tvarle (nn), ubjåleg (nn), unoggen (nn), vermsle (nn), vondle (nn), våskøytt (nn), åleiten (nn), øsnad (nn)

**offensive** (1)
bumse (bm)

**spelling** (5)
glett (bm), klen (bm), løynsk (bm), pyrrhossiger (nn), svimre (nn)

**technical** (47)
agnor (bm), bendsle (nn), bleige (bm), bygsle (bm), bøykje (nn), denotere (nn), dissosiere (nn), erts (nn), fnokk (bm), fondere (nn), forblende (bm), galeas (bm), gylte (bm), handflika (bm), hektografere (bm), holograf (bm), hoppsa (bm), ibidem (nn), idiofon (bm), jelk (bm), jorte (bm), jøkel (bm), kadreie (bm), katatonisk (nn), kjos (bm), kokre (bm), korrelativ (bm), lunne (bm), minuend (bm), morganatisk (bm), myalgisk (nn), nativistisk (bm), nudde (bm), okklusiv (bm), panfobi (nn), patronym (bm), renons (bm), sannkjenne (nn), skjelm (bm), skolm (bm), skolme (bm), skulse (bm), skyldsette (bm), stevje (bm), subtrahend (bm), typisere (nn), verp (bm)

## Sonnet-approved words dropped (37)

**common** (2)
tuske (bm), ørske (bm)

**derived** (1)
skrålsam (nn)

**dialect** (21)
bendast (nn), bidlundsam (nn), drangle (nn), drunten (nn), fjom (nn), geiple (nn), glindre (nn), hjåmete (nn), idast (nn), illgøy (nn), jalme (bm), kvimsen (nn), nogg (nn), ormektast (nn), rengle (nn), skjaltre (nn), skjegle (nn), skripe (nn), tandle (nn), tveite (nn), tvinle (nn)

**dull** (9)
bjekso (bm), blakkert (bm), drambsleg (nn), kokle (nn), kvivitt (bm), ptrotte (bm), snavle (bm), snøfle (bm), snøse (bm)

**spelling** (1)
drusten (nn)

**technical** (3)
manuduksjon (bm), redingot (bm), teksle (nn)

## Added from the 30-40 band (234)

affektasjon (bm), akribi (bm), ambrosisk (bm), ampe (nn), anatema (bm), andvarpe (nn), apoteose (bm), apparisjon (bm), atal (bm), atsprede (bm), aule (bm), auspisier (bm), avbaklig (bm), bagge (bm), bakkenbart (bm), bekvemme (bm), beskøyt (bm), bikse (bm), bivre (nn), blussel (bm), boklærd (bm), brande (bm), briken (nn), bumsete (bm), bæle (nn), damejeanne (bm), dandere (bm), dert (bm), dote (nn), drabeleg (nn), dramb (nn), drasle (nn), drifse (nn), drunse (nn), drøle (bm), drøs (bm), dulpe (bm), elyseisk (bm), evinneleg (nn), filisteri (bm), filistrøs (bm), fjante (nn), fjaske (nn), flangre (nn), flerre (bm), florisant (bm), flurete (nn), forfælande (nn), forfæld (nn), forgape (bm), forgjere (nn), forhippa (nn), formasteleg (nn), fortusta (nn), furdast (nn), gampe (bm), gauke (bm), gauske (nn), gauve (nn), gemenslig (bm), geskjeftig (bm), gjæs (nn), gjønstre (nn), glafse (bm), glense (nn), glohersk (bm), gnafse (bm), gnarre (nn), gnitre (nn), grassat (bm), grisle (bm), grissen (bm), grugge (nn), grukk (bm), gruvle (nn), grymje (nn), habengut (bm), handfrid (nn), heidundrande (nn), henslepe (bm), herdebrei (bm), hildre (bm), hofferdig (bm), hufse (bm), hugal (bm), hugstor (nn), hukre (bm), hustren (bm), hutle (bm), huttetu (bm), idug (nn), illsviden (nn), illudere (bm), infamerende (bm), insiterende (bm), jemini (bm), juglete (bm), kaut (bm), kippskodd (bm), kjekkel (bm), kleinsleg (nn), kløkken (nn), knert (bm), knipsk (bm), knuvl (bm), knøttende (bm), kodilje (bm), konventikkel (bm), kopiøs (bm), kreke (bm), kringmælt (nn), krinkel (bm), krungle (nn), krusle (bm), kulse (bm), kvapsete (nn), kvervle (nn), laban (bm), labbelensk (bm), lemster (bm), ljøske (bm), lurk (bm), løyen (bm), maktstele (nn), mergstele (nn), muge (bm), mulle (bm), myhank (bm), mødesam (nn), mørje (bm), nappast (nn), nauten (nn), nerk (nn), nufse (bm), opulens (bm), ottefull (bm), pardong (bm), perial (bm), pistre (bm), pjalle (bm), pjank (bm), pluriform (bm), pløse (bm), pløsen (bm), populas (bm), proponere (bm), puger (bm), påver (bm), rabalsk (nn), raklete (nn), rapse (bm), rasmus (bm), rekel (bm), rempling (bm), roglete (nn), rulten (bm), ryggjast (nn), råsken (bm), røfle (bm), rønner (bm), sabbete (bm), saltomortale (bm), samfengt (bm), samstave (bm), sibyllinsk (bm), sigen (bm), sjibbolett (bm), sjoge (bm), skaldre (nn), skjerr (bm), skratle (bm), skrubbsvolten (nn), skrynje (nn), slafse (bm), slamp (bm), slarke (bm), sleiken (bm), sliske (bm), slufs (bm), smeik (bm), smeis (bm), snadde (bm), snedden (bm), snulle (nn), snupt (bm), snåp (bm), soignert (bm), sondre (bm), spandabel (bm), spikk (bm), spildre (bm), spjerre (nn), spjert (bm), spræne (nn), stevjast (nn), stimmel (bm), storlåten (nn), strant (bm), surkle (bm), svirpe (nn), svitte (nn), svive (bm), synkverve (bm), tandre (nn), tjåke (bm), trafsete (nn), traud (nn), traurig (bm), trautal (nn), trågjengd (nn), tufs (bm), tuskeleg (nn), tvikrokete (nn), tvirle (nn), tæpe (nn), ufansleg (nn), ulke (bm), uterlig (bm), utæva (nn), vademekum (bm), vadre (bm), valtre (nn), vatre (bm), vederfares (bm), veivle (nn), vrengle (nn), vyrdeleg (nn), våleg (nn), vøle (bm), ydde (bm), yppal (bm), ørsken (bm), ørvæn (nn), øygne (nn)
