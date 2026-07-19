import { motion, type HTMLMotionProps } from "framer-motion";

const container = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

const item = {
  hidden: { opacity: 0, y: 14, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const },
  },
};

/** Wrap a bento-grid; children become `<StaggerItem>` for a cascading mount animation. */
export function StaggerGroup(props: HTMLMotionProps<"div">) {
  return <motion.div variants={container} initial="hidden" animate="show" {...props} />;
}

export function StaggerItem(props: HTMLMotionProps<"div">) {
  return <motion.div variants={item} {...props} />;
}
