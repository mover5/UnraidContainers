import type { SVGProps } from 'react';

const base = (d: string | string[]) =>
  function Icon(props: SVGProps<SVGSVGElement>) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden {...props}>
        {(Array.isArray(d) ? d : [d]).map((p) => (
          <path key={p} d={p} />
        ))}
      </svg>
    );
  };

export const IconBack = base('M15 18l-6-6 6-6');
export const IconPlus = base(['M12 5v14', 'M5 12h14']);
export const IconCheck = base('M5 12.5l4.5 4.5L19 7.5');
export const IconUndo = base(['M9 14L4 9l5-5', 'M4 9h11a5 5 0 010 10h-3']);
export const IconEdit = base(['M4 20h4L19 9l-4-4L4 16v4z', 'M13.5 6.5l4 4']);
export const IconTrash = base(['M4 7h16', 'M10 11v6', 'M14 11v6', 'M6 7l1 13h10l1-13', 'M9 7V4h6v3']);
export const IconUp = base('M6 15l6-6 6 6');
export const IconDown = base('M6 9l6 6 6-6');
export const IconX = base(['M6 6l12 12', 'M18 6L6 18']);
export const IconClipboard = base(['M9 4h6v3H9z', 'M9 5H6v15h12V5h-3', 'M9 12h6', 'M9 16h4']);
export const IconSun = base(['M12 4V2', 'M12 22v-2', 'M4 12H2', 'M22 12h-2', 'M12 17a5 5 0 100-10 5 5 0 000 10z']);
export const IconCopy = base(['M8 8h12v12H8z', 'M4 16V4h12']);
