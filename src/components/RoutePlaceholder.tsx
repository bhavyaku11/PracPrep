import React from "react";
import { NotFound } from "./ui/ghost-404-page";

export interface RoutePlaceholderProps {
  path: string;
  onBack?: () => void;
  onNavigate?: (path: string) => void;
}

export const RoutePlaceholder: React.FC<RoutePlaceholderProps> = ({ path, onBack, onNavigate }) => {
  return (
    <NotFound
      currentPath={path}
      onNavigate={onNavigate || (onBack ? () => onBack() : undefined)}
    />
  );
};

export default RoutePlaceholder;
