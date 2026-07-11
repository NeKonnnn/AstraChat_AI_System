export const FOLLOW_UP_AUTO_GENERATE_KEY = 'follow_up_auto_generate';
export const FOLLOW_UP_SHOW_SCOPE_KEY = 'follow_up_show_scope';
export const FOLLOW_UP_CLICK_ACTION_KEY = 'follow_up_click_action';

export type FollowUpShowScope = 'last' | 'all';
export type FollowUpClickAction = 'insert' | 'send';

export interface FollowUpInterfaceSettings {
  followUpAutoGenerate: boolean;
  followUpShowScope: FollowUpShowScope;
  followUpClickAction: FollowUpClickAction;
}

export function loadFollowUpSettings(): FollowUpInterfaceSettings {
  const savedAuto = localStorage.getItem(FOLLOW_UP_AUTO_GENERATE_KEY);
  const savedScope = localStorage.getItem(FOLLOW_UP_SHOW_SCOPE_KEY);
  const savedClick = localStorage.getItem(FOLLOW_UP_CLICK_ACTION_KEY);

  return {
    followUpAutoGenerate: savedAuto !== null ? savedAuto === 'true' : true,
    followUpShowScope: savedScope === 'all' ? 'all' : 'last',
    followUpClickAction: savedClick === 'send' ? 'send' : 'insert',
  };
}

export function saveFollowUpAutoGenerate(value: boolean): void {
  localStorage.setItem(FOLLOW_UP_AUTO_GENERATE_KEY, String(value));
}

export function saveFollowUpShowScope(value: FollowUpShowScope): void {
  localStorage.setItem(FOLLOW_UP_SHOW_SCOPE_KEY, value);
}

export function saveFollowUpClickAction(value: FollowUpClickAction): void {
  localStorage.setItem(FOLLOW_UP_CLICK_ACTION_KEY, value);
}
