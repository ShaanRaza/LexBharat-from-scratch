import { Button } from "./Button";
import { SearchIcon } from "./icons";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  label: string;
  placeholder?: string;
  disabled?: boolean;
  buttonLabel?: string;
}

/** The big question box. Only shows and reports typing; knows no chat logic. */
export function SearchBar({
  value,
  onChange,
  onSubmit,
  label,
  placeholder,
  disabled,
  buttonLabel = "Ask",
}: Props) {
  return (
    <form
      className="flex items-center gap-2 rounded-card border border-line bg-page p-2 shadow-card focus-within:border-accent"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="search-input">
        {label}
      </label>
      <SearchIcon className="ml-2 shrink-0 text-muted" />
      <input
        id="search-input"
        className="min-w-0 flex-1 bg-transparent px-1 py-2 text-body text-text placeholder:text-muted focus:outline-none"
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
      />
      <Button type="submit" disabled={disabled || value.trim() === ""}>
        {buttonLabel}
      </Button>
    </form>
  );
}
