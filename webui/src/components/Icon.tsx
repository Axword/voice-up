const paths = {
  mic: 'M12 19v3M19 10v2a7 7 0 0 1-14 0v-2M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0Z',
  command: 'M9 7V4a2 2 0 1 0-2 2h10a2 2 0 1 0-2-2v16a2 2 0 1 0 2-2H7a2 2 0 1 0 2 2V7',
  game: 'M6 8h12a4 4 0 0 1 4 4v5a2 2 0 0 1-3.4 1.4L16 16H8l-2.6 2.4A2 2 0 0 1 2 17v-5a4 4 0 0 1 4-4ZM6 10v4M4 12h4M16 11h.01M19 13h.01',
  settings: 'M4 7h16M4 17h16M8 4v6M16 14v6',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  plus: 'M12 5v14M5 12h14',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  external: 'M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5',
  chevron: 'm9 5 7 7-7 7',
  close: 'm6 6 12 12M6 18 18 6',
  check: 'm5 12 4 4L19 6',
  search: 'm21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  code: 'm8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16',
  edit: 'm15 5 4 4M4 20l4-1L20 7a2.1 2.1 0 0 0-3-3L5 16l-1 4Z',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 14h12l1-14M10 10v6M14 10v6',
  copy: 'M9 8V3h12v12h-5M3 8h13v13H3Z',
  click: 'M8 3v4M3 8h4m-2-3 3 3M11 10l9 4-4 2-2 4-4-9Z',
  timer: 'M9 2h6M12 6v7l4 2M19 5l2 2M21 14a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  toggle: 'M12 7h5a5 5 0 0 1 0 10H7A5 5 0 0 1 7 7h5M10 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  play: 'm8 5 11 7-11 7V5Z',
  pause: 'M8 5v14M16 5v14',
  sun: 'M12 2v2M12 20v2M2 12h2M20 12h2m-3-8-2 2M5 19l2-2M5 5l2 2m10 10 2 2M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  moon: 'M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z',
  keyboard: 'M3 5h18v14H3ZM6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 11h.01M10 11h.01M14 11h.01M18 11h.01M7 15h10',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  upload: 'M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5',
  release: 'M8 13V7a2 2 0 0 1 4 0v5-8a2 2 0 0 1 4 0v8-6a2 2 0 0 1 4 0v10c0 4-3 6-7 6-3 0-5-2-7-5l-3-4a2 2 0 0 1 3-2l2 2',
  refresh: 'M20 7V3l-4 1M20 7a9 9 0 1 0 1 9',
  volume: 'M11 4 5 8H2v8h3l6 4V4ZM15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14',
} as const;
export type IconName = keyof typeof paths;
export function Icon({name, size = 18}: {name: IconName; size?: number}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}
