import {describe, expect, it} from 'vitest'
import {parseRichText} from '../src/chat/RichText'
import {href, mapLegacy, parseHash} from '../src/app/router'

describe('rich text (*action* with odd/even backslash escapes)', () => {
  it('marks *spans* as actions and keeps newlines', () => {
    expect(parseRichText('*nods*\nOK')).toEqual([{text: 'nods', action: true}, {text: '\nOK', action: false}])
  })
  it('an odd run of backslashes escapes the star (one backslash consumed)', () => {
    expect(parseRichText('a \\*b* c')).toEqual([{text: 'a *b* c', action: false}])
    expect(parseRichText('\\\\\\*x*')).toEqual([{text: '\\\\*x*', action: false}])
  })
  it('an even run keeps every backslash and the star still delimits', () => {
    expect(parseRichText('\\\\*x*')).toEqual([{text: '\\\\', action: false}, {text: 'x', action: true}])
  })
  it('the same rule applies inside a span', () => {
    expect(parseRichText('*a\\*b*')).toEqual([{text: 'a*b', action: true}])
  })
  it('unclosed or empty stars stay literal; HTML stays text', () => {
    expect(parseRichText('5 * 3')).toEqual([{text: '5 * 3', action: false}])
    expect(parseRichText('**')).toEqual([{text: '**', action: false}])
    expect(parseRichText('<img src=x onerror=alert(1)>')).toEqual([{text: '<img src=x onerror=alert(1)>', action: false}])
  })
})

describe('router', () => {
  it('parses every page route', () => {
    expect(parseHash('')).toEqual({name: 'root'})
    expect(parseHash('#/discover?tab=games&q=abc')).toEqual({name: 'discover', tab: 'games', q: 'abc'})
    expect(parseHash('#/discover?tab=bogus')).toEqual({name: 'discover', tab: 'all', q: ''})
    expect(parseHash('#/friends/fr_1')).toEqual({name: 'chat', friendId: 'fr_1'})
    expect(parseHash('#/stories/s1/prepare?v=2&with=fr_9&from=%23%2Ffriends')).toEqual({name: 'storyPrepare', id: 's1', version: '2', withFriend: 'fr_9', from: '#/friends'})
    expect(parseHash('#/play/game/gs_1')).toEqual({name: 'gamePlay', sessionId: 'gs_1'})
    expect(parseHash('#/recent?archived=1')).toEqual({name: 'recent', archived: true})
    expect(parseHash('#/create/w1')).toEqual({name: 'work', workId: 'w1'})
    expect(parseHash('#/nope').name).toBe('notFound')
  })
  it('maps legacy #/companions deep links to the named object, never the default home', () => {
    expect(mapLegacy('#/companions?view=friends&gameSession=gs_7')).toBe('#/play/game/gs_7')
    expect(mapLegacy('#/companions?storySession=ss_2')).toBe('#/play/story/ss_2')
    expect(mapLegacy('#/companions?view=friends&friend=fr_3')).toBe('#/friends/fr_3')
    expect(mapLegacy('#/companions?story=story-a&version=3')).toBe('#/stories/story-a?v=3')
    expect(mapLegacy('#/companions?view=create')).toBe('#/create')
    expect(mapLegacy('#/discover')).toBeNull()
  })
  it('href helpers round-trip through the parser', () => {
    expect(parseHash(href.gamePrepare('cabo', 'fr_1', '#/friends/fr_1'))).toEqual({name: 'gamePrepare', gameId: 'cabo', withFriend: 'fr_1', from: '#/friends/fr_1'})
    expect(parseHash(href.storyPrepare('story-x', '1'))).toMatchObject({name: 'storyPrepare', id: 'story-x', version: '1', withFriend: null})
  })
})
