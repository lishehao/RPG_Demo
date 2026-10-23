import React from "react"
import {Composition} from "remotion"
import {DemoTrailer, demoTrailerFrames} from "./DemoTrailer"
import {TinyStoriesTrailer} from "./TinyStoriesTrailer"

export const Root: React.FC = () => (
  <>
    <Composition
      id="TinyStoriesTrailer"
      component={TinyStoriesTrailer}
      durationInFrames={1530}
      fps={30}
      width={1920}
      height={1080}
    />
    <Composition
      id="DemoTrailer"
      component={DemoTrailer}
      durationInFrames={demoTrailerFrames}
      fps={30}
      width={1920}
      height={1080}
    />
  </>
)
