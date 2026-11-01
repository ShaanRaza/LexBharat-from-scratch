// A heading that is a long stored string (a citation string, a section title, an Act name)
// must not take seven lines at title size on a phone. Short headings keep the title size.
export const LONG_HEADING = 60;
export const headingSize = (text: string) => (text.length > LONG_HEADING ? "text-lead" : "text-title");
