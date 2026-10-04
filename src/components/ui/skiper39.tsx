"use client";

import { gsap } from "gsap";
import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export interface CrowdCanvasProps {
  src: string;
  rows?: number;
  cols?: number;
  className?: string;
  maxPeeps?: number;
}

interface Stage {
  width: number;
  height: number;
}

interface PeepResetProps {
  startX: number;
  startY: number;
  endX: number;
}

interface Peep {
  image: HTMLImageElement;
  rect: [number, number, number, number];
  width: number;
  height: number;
  drawArgs: [HTMLImageElement, number, number, number, number, number, number, number, number];
  x: number;
  y: number;
  anchorY: number;
  scaleX: number;
  walk: gsap.core.Timeline | null;
  setRect: (rect: [number, number, number, number]) => void;
  render: (ctx: CanvasRenderingContext2D) => void;
}

const CrowdCanvas = ({
  src,
  rows = 15,
  cols = 7,
  className,
  maxPeeps,
}: CrowdCanvasProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let isMounted = true;
    let isVisible = true;
    let tickerAttached = false;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const config = {
      src,
      rows,
      cols,
    };

    // UTILS
    const randomRange = (min: number, max: number) =>
      min + Math.random() * (max - min);
    const randomIndex = <T,>(array: T[]) => (randomRange(0, array.length) | 0);
    const removeFromArray = <T,>(array: T[], i: number): T => array.splice(i, 1)[0];
    const removeItemFromArray = <T,>(array: T[], item: T): T =>
      removeFromArray(array, array.indexOf(item));
    const removeRandomFromArray = <T,>(array: T[]): T =>
      removeFromArray(array, randomIndex(array));
    const getRandomFromArray = <T,>(array: T[]): T => array[randomIndex(array)];

    // TWEEN FACTORIES
    const resetPeep = ({ stage, peep }: { stage: Stage; peep: Peep }): PeepResetProps => {
      const direction = Math.random() > 0.5 ? 1 : -1;
      const offsetY = 100 - 250 * gsap.parseEase("power2.in")(Math.random());
      const startY = stage.height - peep.height + offsetY;
      let startX: number;
      let endX: number;

      if (direction === 1) {
        startX = -peep.width;
        endX = stage.width;
        peep.scaleX = 1;
      } else {
        startX = stage.width + peep.width;
        endX = 0;
        peep.scaleX = -1;
      }

      peep.x = startX;
      peep.y = startY;
      peep.anchorY = startY;

      return {
        startX,
        startY,
        endX,
      };
    };

    const normalWalk = ({ peep, props }: { peep: Peep; props: PeepResetProps }): gsap.core.Timeline => {
      const { startY, endX } = props;
      const xDuration = 10;
      const yDuration = 0.25;

      const tl = gsap.timeline();
      tl.timeScale(randomRange(0.5, 1.5));
      tl.to(
        peep,
        {
          duration: xDuration,
          x: endX,
          ease: "none",
        },
        0,
      );
      tl.to(
        peep,
        {
          duration: yDuration,
          repeat: xDuration / yDuration,
          yoyo: true,
          y: startY - 10,
        },
        0,
      );

      return tl;
    };

    const walks = [normalWalk];

    // FACTORY FUNCTIONS
    const createPeep = ({
      image,
      rect,
    }: {
      image: HTMLImageElement;
      rect: [number, number, number, number];
    }): Peep => {
      const peep: Peep = {
        image,
        rect: [0, 0, 0, 0],
        width: 0,
        height: 0,
        drawArgs: [image, 0, 0, 0, 0, 0, 0, 0, 0],
        x: 0,
        y: 0,
        anchorY: 0,
        scaleX: 1,
        walk: null,
        setRect: (newRect: [number, number, number, number]) => {
          peep.rect = newRect;
          peep.width = newRect[2];
          peep.height = newRect[3];
          peep.drawArgs = [
            peep.image,
            newRect[0],
            newRect[1],
            newRect[2],
            newRect[3],
            0,
            0,
            peep.width,
            peep.height,
          ];
        },
        render: (targetCtx: CanvasRenderingContext2D) => {
          targetCtx.save();
          targetCtx.translate(peep.x, peep.y);
          targetCtx.scale(peep.scaleX, 1);
          targetCtx.drawImage(
            peep.image,
            peep.rect[0],
            peep.rect[1],
            peep.rect[2],
            peep.rect[3],
            0,
            0,
            peep.width,
            peep.height,
          );
          targetCtx.restore();
        },
      };

      peep.setRect(rect);
      return peep;
    };

    // MAIN
    const img = new Image();
    img.crossOrigin = "anonymous";

    const stage: Stage = {
      width: 0,
      height: 0,
    };

    const allPeeps: Peep[] = [];
    const availablePeeps: Peep[] = [];
    const crowd: Peep[] = [];

    const createPeeps = () => {
      const { rows, cols } = config;
      const { naturalWidth: width, naturalHeight: height } = img;
      if (!width || !height) return;

      const total = rows * cols;
      const rectWidth = width / rows;
      const rectHeight = height / cols;

      allPeeps.length = 0;
      for (let i = 0; i < total; i++) {
        allPeeps.push(
          createPeep({
            image: img,
            rect: [
              (i % rows) * rectWidth,
              ((i / rows) | 0) * rectHeight,
              rectWidth,
              rectHeight,
            ],
          }),
        );
      }
    };

    const addPeepToCrowd = (): Peep | null => {
      if (!isMounted || !availablePeeps.length) return null;
      const peep = removeRandomFromArray(availablePeeps);
      const walk = getRandomFromArray(walks)({
        peep,
        props: resetPeep({
          peep,
          stage,
        }),
      }).eventCallback("onComplete", () => {
        if (!isMounted) return;
        removePeepFromCrowd(peep);
        addPeepToCrowd();
      });

      peep.walk = walk;

      crowd.push(peep);
      crowd.sort((a, b) => a.anchorY - b.anchorY);

      return peep;
    };

    const removePeepFromCrowd = (peep: Peep) => {
      removeItemFromArray(crowd, peep);
      availablePeeps.push(peep);
    };

    const initCrowd = () => {
      if (!isMounted) return;
      const limit = maxPeeps ? Math.min(maxPeeps, availablePeeps.length) : availablePeeps.length;
      let count = 0;
      while (availablePeeps.length && count < limit) {
        const added = addPeepToCrowd();
        if (added && added.walk) {
          added.walk.progress(Math.random());
        }
        count++;
      }
    };

    const render = () => {
      if (!canvas || !isMounted || !isVisible) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.scale(dpr, dpr);

      for (let i = 0; i < crowd.length; i++) {
        crowd[i].render(ctx);
      }

      ctx.restore();
    };

    const resize = () => {
      if (!canvas || !isMounted) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      stage.width = canvas.clientWidth;
      stage.height = canvas.clientHeight;
      canvas.width = stage.width * dpr;
      canvas.height = stage.height * dpr;

      crowd.forEach((peep) => {
        if (peep.walk) peep.walk.kill();
      });

      crowd.length = 0;
      availablePeeps.length = 0;
      availablePeeps.push(...allPeeps);

      initCrowd();
      render();
    };

    const attachTicker = () => {
      if (!tickerAttached && !prefersReducedMotion) {
        gsap.ticker.add(render);
        tickerAttached = true;
      }
    };

    const detachTicker = () => {
      if (tickerAttached) {
        gsap.ticker.remove(render);
        tickerAttached = false;
      }
    };

    const init = () => {
      if (!isMounted) return;
      createPeeps();
      resize();

      if (prefersReducedMotion) {
        // Reduced motion: draw static crowd illustration without starting ticker
        crowd.forEach((peep) => {
          if (peep.walk) peep.walk.pause();
        });
        render();
      } else {
        attachTicker();
      }
    };

    img.onload = () => {
      if (isMounted) init();
    };

    img.onerror = () => {
      // Fallback to local asset if external CDN fails
      if (config.src !== "/assets/peeps-sprite.png") {
        img.src = "/assets/peeps-sprite.png";
      } else {
        console.warn("Failed to load CrowdCanvas sprite image.");
      }
    };

    img.src = config.src;

    const handleResize = () => {
      if (isMounted) resize();
    };

    window.addEventListener("resize", handleResize);

    // Pause animation when off-screen to save battery/resources
    let observer: IntersectionObserver | null = null;
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          const entry = entries[0];
          isVisible = entry.isIntersecting;
          if (isVisible) {
            attachTicker();
          } else {
            detachTicker();
          }
        },
        { threshold: 0.05 },
      );
      observer.observe(canvas);
    }

    return () => {
      isMounted = false;
      img.onload = null;
      img.onerror = null;
      window.removeEventListener("resize", handleResize);
      if (observer) {
        observer.disconnect();
      }
      detachTicker();
      crowd.forEach((peep) => {
        if (peep.walk) peep.walk.kill();
      });
    };
  }, [src, rows, cols, maxPeeps]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      tabIndex={-1}
      className={cn(
        "pointer-events-none absolute bottom-0 h-full w-full select-none",
        className,
      )}
    />
  );
};

interface Skiper39Props {
  className?: string;
  children?: React.ReactNode;
  src?: string;
  rows?: number;
  cols?: number;
  canvasClassName?: string;
  showDefaultLabel?: boolean;
}

const Skiper39 = ({
  className,
  children,
  src = "https://cdn.21st.dev/assets/localized/abdb8990a7bef8c2f5af3e45f0a3c969c4b0603fba8be92e81347de4ea4e1ed7.png",
  rows = 15,
  cols = 7,
  canvasClassName,
  showDefaultLabel = false,
}: Skiper39Props) => {
  return (
    <div className={cn("relative h-full w-full bg-white text-black overflow-hidden", className)}>
      {showDefaultLabel && (
        <div className="top-22 absolute left-1/2 grid -translate-x-1/2 content-start justify-items-center gap-6 text-center text-black z-10 pointer-events-none">
          <span className="relative max-w-[12ch] text-xs uppercase leading-tight opacity-40 after:absolute after:left-1/2 after:top-full after:h-16 after:w-px after:bg-gradient-to-b after:from-white after:to-black after:content-['']">
            Crowd Canvas
          </span>
        </div>
      )}

      {children}

      <div className="absolute bottom-0 h-full w-full pointer-events-none">
        <CrowdCanvas
          src={src}
          rows={rows}
          cols={cols}
          className={canvasClassName}
        />
      </div>
    </div>
  );
};

export { CrowdCanvas, Skiper39 };
export default Skiper39;

/**
 * Skiper 39 Canvas_Landing_004 — React + Canvas
 * Inspired by and adapted from https://codepen.io/zadvorsky/pen/xxwbBQV
 * illustration by https://www.openpeeps.com/
 * We respect the original creators. This is an inspired rebuild with our own taste and does not claim any ownership.
 * These animations aren't associated with the codepen.io . They're independent recreations meant to study interaction design
 *
 * License & Usage:
 * - Free to use and modify in both personal and commercial projects.
 * - Attribution to Skiper UI is required when using the free version.
 * - No attribution required with Skiper UI Pro.
 *
 * Feedback and contributions are welcome.
 *
 * Author: @gurvinder-singh02
 * Website: https://gxuri.me
 * Twitter: https://x.com/Gur__vi
 */
