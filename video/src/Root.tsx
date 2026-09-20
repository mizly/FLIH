import "./index.css";
import { Composition } from "remotion";
import { FlihVideo } from "./Composition";
import { KineticVideo } from "./kinetic/KineticVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="FLIH-Kinetic"
        component={KineticVideo}
        durationInFrames={1021}
        fps={60}
        width={1920}
        height={1080}
      />
      <Composition
        id="FLIH"
        component={FlihVideo}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
